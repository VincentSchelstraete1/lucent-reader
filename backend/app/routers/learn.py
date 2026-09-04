from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter
from sqlalchemy import select

from app.auth_dependencies import get_current_user, require_csrf
from app.database import get_db
from app.models.auth import User
from app.models.document import Document
from app.models.learn import LearnAttempt, LearnSession
from app.models.note import Note
from app.models.source import Source
from app.schemas.learn import ConceptEvidence, LearnEvaluation, LearnHintResponse, LearnResponseRequest, LearnSessionCreateRequest, LearnSessionReport, LearnSessionResponse, LearnStep, MultipleChoiceStep, ShortAnswerStep, TutorAction
from app.services.learn_engine import build_learn_plan, evaluate_step, plan_fingerprint, public_step
from app.services.learn_tutor import diagnose_response

router = APIRouter()
STEP_ADAPTER = TypeAdapter(LearnStep)

def _owned_document(db, document_id: int, user: User) -> Document:
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document: raise HTTPException(status_code=404, detail="Study material not found")
    return document

def _latest_note(db, document_id: int) -> Note | None:
    return db.execute(select(Note).where(Note.document_id == document_id, Note.content_type == "section_note").order_by(Note.updated_at.desc())).scalars().first()

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _parse_step(raw: dict):
    try: return STEP_ADAPTER.validate_python(raw)
    except Exception: return None

def _concepts(session: LearnSession) -> list[dict]: return list((session.state or {}).get("concepts") or [])

def _concept_for(session: LearnSession, objective: dict) -> dict:
    found = next((item for item in _concepts(session) if item.get("conceptId") == objective.get("id")), None)
    return found or {"conceptId": objective.get("id"), "title": objective.get("title", "Concept"), "state": "NOT_SEEN", "attempts": 0, "correct": 0, "partiallyCorrect": 0, "incorrect": 0, "insufficientEvidence": 0, "hintsUsed": 0, "interactionTypes": [], "misconceptions": [], "immediateSuccess": False, "delayedSuccess": False, "sourceSectionIds": objective.get("sourceSectionIds", []), "sourceBlockIds": objective.get("sourceBlockIds", [])}

def _action_for(step, objective: dict, concept: dict, revisit: bool = False, remediation: str | None = None) -> TutorAction:
    mapping = {"teach": "teach_concept", "multiple_choice": "ask_multiple_choice", "short_answer": "ask_free_response", "numeric": "ask_free_response", "prediction": "ask_prediction", "ordering": "ask_ordering", "problem": "ask_free_response", "walkthrough": "show_process_visual"}
    remediation_map = {"simplify": "decrease_difficulty", "example": "give_example", "prerequisite": "revisit_prerequisite", "change_modality": "give_analogy", "revisit": "revisit_concept"}
    action_type = remediation_map.get(remediation or "") or ("revisit_concept" if revisit else mapping.get(step.type, "teach_concept"))
    if concept.get("state") in {"STRUGGLING", "NEEDS_REVIEW"} and not revisit and step.type not in {"teach", "walkthrough"}: action_type = "clarify_definition"
    return TutorAction(id=f"action-{step.id}", type=action_type, conceptId=objective.get("id", "concept"), stepId=step.id, rationale="Revisit the concept with a different validated check." if revisit else "A bounded teaching or checking action matched to current evidence.")

def _report(session: LearnSession) -> LearnSessionReport:
    objectives = session.plan.get("objectives", []); by_id = {item.get("conceptId"): item for item in _concepts(session)}
    covered, demonstrated, developing, struggles, needs_review, not_covered = [], [], [], [], [], []
    for objective in objectives:
        item = by_id.get(objective.get("id"), {}); state = item.get("state", "NOT_SEEN"); title = objective.get("title", "Concept")
        if state == "NOT_SEEN": not_covered.append(title)
        else: covered.append(title)
        if state == "DEMONSTRATED": demonstrated.append(title)
        elif state in {"DEVELOPING", "INTRODUCED"}: developing.append(title)
        if state == "STRUGGLING": struggles.append(f"{title}: " + (item.get("misconceptions") or ["understanding is not yet consistent"])[-1])
        if state in {"NEEDS_REVIEW", "STRUGGLING"}: needs_review.append(title)
    queue = list((session.state or {}).get("revisitQueue") or []); next_focus = [by_id.get(cid, {}).get("title", cid) for cid in queue]
    next_focus.extend(needs_review)
    return LearnSessionReport(covered=covered, demonstrated=demonstrated, developing=developing, struggles=struggles, needsReview=list(dict.fromkeys(needs_review)), notCovered=not_covered, nextFocus=list(dict.fromkeys(next_focus)), stopped=session.status == "stopped")

def _completion_met(session: LearnSession) -> bool:
    concepts = _concepts(session); objectives = session.plan.get("objectives", [])
    if len(concepts) < len(objectives) or (session.state or {}).get("revisitQueue"): return False
    for objective in objectives:
        item = next((c for c in concepts if c.get("conceptId") == objective.get("id")), {})
        if item.get("state") == "NOT_SEEN" or item.get("state") in {"STRUGGLING", "NEEDS_REVIEW"} or not item.get("correct"): return False
    return True

def _session_payload(session: LearnSession, feedback: str | None = None, feedback_kind: str | None = None, evaluation: LearnEvaluation | None = None) -> LearnSessionResponse:
    plan = session.plan or {}; objectives = plan.get("objectives", []); state = session.state or {}; current = None; objective_title = None; action = None
    if session.status == "active" and session.objective_index < len(objectives):
        objective = objectives[session.objective_index]; objective_title = objective.get("title"); steps = objective.get("steps", [])
        if session.step_index < len(steps):
            parsed = _parse_step(steps[session.step_index])
            if parsed:
                hints_used = int((state.get("hints") or {}).get(parsed.id, 0)); current = public_step(parsed, hints_used); action = _action_for(parsed, objective, _concept_for(session, objective), bool(state.get("revisitMode")), state.get("lastRemediation"))
    concepts = [ConceptEvidence.model_validate(item) for item in _concepts(session)]
    report = LearnSessionReport.model_validate(session.report) if session.report else None
    return LearnSessionResponse(id=str(session.id), documentId=session.document_id, goal=session.goal, familiarity=session.familiarity, status=session.status, objectiveIndex=session.objective_index, stepIndex=session.step_index, objectiveCount=len(objectives), objectiveTitle=objective_title, step=current, feedback=feedback, feedbackKind=feedback_kind, hintsUsed=int((state.get("hints") or {}).get(current.id, 0)) if current else 0, completedObjectives=sum(1 for c in concepts if c.state == "DEMONSTRATED"), weakObjectives=[c.concept_id for c in concepts if c.state in {"NEEDS_REVIEW", "STRUGGLING"}], action=action, evaluation=evaluation, conceptStates=concepts, report=report, endedReason=session.ended_reason)

def _get_owned_session(db, session_id: UUID, user: User) -> LearnSession:
    session = db.execute(select(LearnSession).where(LearnSession.id == session_id, LearnSession.user_id == user.id)).scalar_one_or_none()
    if not session: raise HTTPException(status_code=404, detail="Learning session not found")
    return session

def _initial_state(db, user: User, document_id: int, plan: dict) -> dict:
    prior = db.execute(select(LearnSession).where(LearnSession.user_id == user.id, LearnSession.document_id == document_id).order_by(LearnSession.updated_at.desc())).scalars().first()
    prior_map = {c.get("conceptId"): c for c in ((prior.state or {}).get("concepts") if prior else [])}; concepts = []
    for objective in plan.get("objectives", []):
        previous = dict(prior_map.get(objective.get("id"), {})); concepts.append({"conceptId": objective.get("id"), "title": objective.get("title", "Concept"), "state": previous.get("state", "NOT_SEEN"), "attempts": 0, "correct": 0, "partiallyCorrect": 0, "incorrect": 0, "insufficientEvidence": 0, "hintsUsed": 0, "interactionTypes": [], "misconceptions": previous.get("misconceptions", []), "immediateSuccess": False, "delayedSuccess": False, "sourceSectionIds": objective.get("sourceSectionIds", []), "sourceBlockIds": objective.get("sourceBlockIds", []), "priorEvidence": previous.get("correct", 0), "lastResult": None})
    queue = [c["conceptId"] for c in concepts if c["state"] in {"DEMONSTRATED", "NEEDS_REVIEW", "STRUGGLING"}]
    return {"attempts": {}, "hints": {}, "concepts": concepts, "revisitQueue": queue, "revisitMode": bool(queue), "completed": []}

@router.post("/documents/{document_id}/learn-sessions", response_model=LearnSessionResponse, dependencies=[Depends(require_csrf)])
def create_learn_session(document_id: int, request: LearnSessionCreateRequest, db=Depends(get_db), user: User = Depends(get_current_user)):
    document = _owned_document(db, document_id, user); note = _latest_note(db, document_id)
    if not note: raise HTTPException(status_code=409, detail="Create notes for this material before starting Learn")
    try: payload = json.loads(note.content)
    except (TypeError, ValueError): raise HTTPException(status_code=409, detail="The notes for this material are unavailable")
    fingerprint = plan_fingerprint(payload, request.goal, request.familiarity)
    if not request.restart:
        existing = db.execute(select(LearnSession).where(LearnSession.user_id == user.id, LearnSession.document_id == document.id, LearnSession.plan_fingerprint == fingerprint, LearnSession.status == "active").order_by(LearnSession.updated_at.desc())).scalars().first()
        if existing: return _session_payload(existing)
    plan = build_learn_plan(payload, request.goal, request.familiarity); plan_data = plan.model_dump(by_alias=True)
    session = LearnSession(user_id=user.id, document_id=document.id, note_id=note.id, goal=request.goal, familiarity=request.familiarity, plan=plan_data, objective_index=0, step_index=0, state=_initial_state(db, user, document.id, plan_data), status="active", plan_fingerprint=fingerprint)
    db.add(session); db.commit(); db.refresh(session); return _session_payload(session)

@router.get("/learn-sessions/{session_id}", response_model=LearnSessionResponse)
def get_learn_session(session_id: UUID, db=Depends(get_db), user: User = Depends(get_current_user)): return _session_payload(_get_owned_session(db, session_id, user))

@router.get("/documents/{document_id}/learn-sessions/active", response_model=LearnSessionResponse | None)
def get_active_learn_session(document_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    _owned_document(db, document_id, user); session = db.execute(select(LearnSession).where(LearnSession.document_id == document_id, LearnSession.user_id == user.id, LearnSession.status == "active").order_by(LearnSession.updated_at.desc())).scalars().first(); return _session_payload(session) if session else None

@router.post("/learn-sessions/{session_id}/hints", response_model=LearnHintResponse, dependencies=[Depends(require_csrf)])
def get_learn_hint(session_id: UUID, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if session.status != "active": raise HTTPException(status_code=409, detail="This learning session is no longer active")
    parsed = _parse_step(session.plan["objectives"][session.objective_index]["steps"][session.step_index])
    if not parsed: raise HTTPException(status_code=409, detail="This teaching step is unavailable")
    state = dict(session.state or {}); hints = dict(state.get("hints") or {}); used = int(hints.get(parsed.id, 0))
    if used >= len(parsed.hints): raise HTTPException(status_code=409, detail="No more hints are available")
    hints[parsed.id] = used + 1; state["hints"] = hints; objective_id = session.plan["objectives"][session.objective_index]["id"]
    for concept in state.get("concepts", []):
        if concept.get("conceptId") == objective_id: concept["hintsUsed"] = int(concept.get("hintsUsed", 0)) + 1
    session.state = state; db.commit(); return LearnHintResponse(hint=parsed.hints[used], hintsUsed=used + 1)

def _next_objective(session: LearnSession, state: dict) -> None:
    objectives = session.plan.get("objectives", []); queue = list(state.get("revisitQueue") or []); concepts = {c.get("conceptId"): c for c in state.get("concepts", [])}
    target = queue[0] if queue else next((o.get("id") for o in objectives if concepts.get(o.get("id"), {}).get("state") == "NOT_SEEN"), None)
    if target is None: target = next((o.get("id") for o in objectives if concepts.get(o.get("id"), {}).get("state") not in {"DEMONSTRATED"}), None)
    if target is None: session.objective_index = len(objectives); session.step_index = 0; return
    session.objective_index = next(i for i, o in enumerate(objectives) if o.get("id") == target); steps = objectives[session.objective_index].get("steps", [])
    session.step_index = next((i for i, raw in enumerate(steps) if _parse_step(raw) and _parse_step(raw).type not in {"teach", "walkthrough"}), 0); state["revisitMode"] = bool(queue and target == queue[0])

def _append_remediation(session: LearnSession, objective: dict, failed_step) -> int:
    """Create one alternate, validated check instead of repeating a prompt."""
    plan = deepcopy(session.plan)
    objective = next(item for item in plan["objectives"] if item.get("id") == objective.get("id"))
    steps = objective.setdefault("steps", [])
    repair_id = f"{failed_step.id}-repair-{len(steps)}"
    if failed_step.type in {"multiple_choice", "prediction", "ordering"}:
        repair = ShortAnswerStep(id=repair_id, type="short_answer", title="Try the idea another way", prompt="In one short phrase, what is the key relationship here?", acceptedAnswers=[failed_step.feedback_incorrect or "the source-grounded relationship"], requiredConcepts=[], feedbackIncorrect="Use the explanation above to name the relationship.", sourceSectionIds=failed_step.source_section_ids, sourceBlockIds=failed_step.source_block_ids)
    else:
        repair = MultipleChoiceStep(id=repair_id, type="multiple_choice", title="Check the key distinction", prompt="Which response best matches the teaching point?", options=[{"id": "a", "label": "The source-grounded relationship described above."}, {"id": "b", "label": "An unrelated detail."}], answerId="a", feedbackIncorrect="Look for the relationship that explains why the concept works.", sourceSectionIds=failed_step.source_section_ids, sourceBlockIds=failed_step.source_block_ids)
    steps.append(repair.model_dump(by_alias=True))
    session.plan = plan
    return len(steps) - 1

@router.post("/learn-sessions/{session_id}/responses", response_model=LearnSessionResponse, dependencies=[Depends(require_csrf)])
def submit_learn_response(session_id: UUID, request: LearnResponseRequest, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if session.status != "active": return _session_payload(session, feedback="This session is no longer active.", feedback_kind="info")
    objective = session.plan["objectives"][session.objective_index]; step = _parse_step(objective["steps"][session.step_index])
    if not step: session.step_index += 1; db.commit(); return _session_payload(session, feedback="That step was skipped because it was unavailable.", feedback_kind="info")
    state = dict(session.state or {}); attempts = dict(state.get("attempts") or {}); attempt_number = int(attempts.get(step.id, 0)) + 1; attempts[step.id] = attempt_number; state["attempts"] = attempts
    evaluation = evaluate_step(step, response=request.response, option_id=request.option_id, ordered_ids=request.ordered_ids)
    if request.response and step.type in {"short_answer", "problem", "numeric"}:
        expected = " ".join(getattr(step, "accepted_answers", []) or []) or str(getattr(step, "answer", ""))
        evaluation = diagnose_response(prompt=getattr(step, "prompt", ""), expected=expected, response=request.response, source_context=" ".join(objective.get("sourceSectionIds", [])), fallback=evaluation)
    concepts = [dict(c) for c in state.get("concepts", [])]; concept = next((c for c in concepts if c.get("conceptId") == objective["id"]), _concept_for(session, objective)); concept["attempts"] = int(concept.get("attempts", 0)) + (0 if evaluation.result == "insufficient_evidence" else 1); concept["lastSeen"] = _now(); concept["lastResult"] = evaluation.result
    state["lastRemediation"] = evaluation.remediation_category if evaluation.result in {"incorrect", "partially_correct"} else None
    concept.setdefault("firstSeen", concept["lastSeen"])
    if step.type not in {"teach", "walkthrough"} and step.type not in concept.get("interactionTypes", []): concept.setdefault("interactionTypes", []).append(step.type)
    if evaluation.result == "correct": concept["correct"] = int(concept.get("correct", 0)) + 1; concept["immediateSuccess"] = True; concept["state"] = "DEMONSTRATED" if concept.get("delayedSuccess") or concept.get("priorEvidence", 0) else "DEVELOPING"
    elif evaluation.result == "partially_correct": concept["partiallyCorrect"] = int(concept.get("partiallyCorrect", 0)) + 1; concept["state"] = "DEVELOPING"
    elif evaluation.result == "incorrect":
        concept["incorrect"] = int(concept.get("incorrect", 0)) + 1; concept["state"] = "STRUGGLING" if concept["incorrect"] >= 2 else "DEVELOPING"; misconception = evaluation.misconception
        if misconception and misconception not in concept.setdefault("misconceptions", []): concept["misconceptions"].append(misconception)
    else: concept["insufficientEvidence"] = int(concept.get("insufficientEvidence", 0)) + 1; concept["state"] = "INTRODUCED"
    state["concepts"] = [concept if c.get("conceptId") == objective["id"] else c for c in concepts]
    db.add(LearnAttempt(session_id=session.id, objective_id=objective["id"], step_id=step.id, step_type=step.type, response=request.response or request.option_id or (",".join(request.ordered_ids or [])), result=evaluation.result, attempt_number=attempt_number, hints_used=int((state.get("hints") or {}).get(step.id, 0)), evaluation=evaluation.model_dump(by_alias=True)))
    feedback = step.feedback_correct if evaluation.result == "correct" else step.feedback_incorrect or evaluation.misconception or evaluation.evidence
    if evaluation.result in {"incorrect", "partially_correct"}:
        queue = list(state.get("revisitQueue") or []); state["revisitQueue"] = queue if objective["id"] in queue else queue + [objective["id"]]
    elif objective["id"] in state.get("revisitQueue", []) and state.get("revisitMode"):
        state["revisitQueue"] = [cid for cid in state["revisitQueue"] if cid != objective["id"]]; concept["delayedSuccess"] = True; concept["state"] = "DEMONSTRATED"; state["revisitMode"] = False
    session.state = state
    if evaluation.result in {"incorrect", "partially_correct"}:
        steps = objective.get("steps", [])
        next_idx = next((i for i in range(session.step_index + 1, len(steps)) if _parse_step(steps[i]) and _parse_step(steps[i]).type not in {"teach", "walkthrough"}), None)
        session.step_index = next_idx if next_idx is not None else _append_remediation(session, objective, step)
    else:
        session.step_index += 1
    current_steps = session.plan.get("objectives", [])[session.objective_index].get("steps", []) if session.objective_index < len(session.plan.get("objectives", [])) else []
    if session.step_index >= len(current_steps): _next_objective(session, state)
    if _completion_met(session): session.status = "completed"; session.ended_reason = "evidence_sufficient"; session.report = _report(session).model_dump(by_alias=True)
    db.commit(); return _session_payload(session, feedback=feedback, feedback_kind="correct" if evaluation.result == "correct" else "incorrect" if evaluation.result in {"incorrect", "partially_correct"} else "info", evaluation=evaluation)

@router.post("/learn-sessions/{session_id}/stop", response_model=LearnSessionResponse, dependencies=[Depends(require_csrf)])
def stop_learn_session(session_id: UUID, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if session.status == "active": session.status = "stopped"; session.ended_reason = "user_stopped"; session.report = _report(session).model_dump(by_alias=True); db.commit()
    return _session_payload(session)
