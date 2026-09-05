from __future__ import annotations

import json
import re
import time
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
from app.models.learn import LearnAttempt, LearnSession, LearnTutorEvent
from app.models.note import Note
from app.models.source import Source
from app.schemas.learn import AskLucentRequest, AskLucentResponse, ConceptEvidence, LearnEvaluation, LearnHintResponse, LearnResponseRequest, LearnSessionCreateRequest, LearnSessionReport, LearnSessionResponse, LearnStep, MultipleChoiceStep, ShortAnswerStep, TutorAction
from app.services.learn_engine import build_learn_plan, evaluate_step, plan_fingerprint, public_step
from app.services.learn_tutor import ask_lucent_model, diagnose_response
from app.services.retrieval import retrieve_note_context

router = APIRouter()
STEP_ADAPTER = TypeAdapter(LearnStep)
_ASK_RATE: dict[str, list[float]] = {}
_ASK_WINDOW_SECONDS = 60
_ASK_MAX_REQUESTS = 12

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

def _diagnosis_type(result: str, step_type: str, attempts: int, misconception: str | None) -> str:
    if result == "insufficient_evidence": return "INSUFFICIENT_EVIDENCE"
    if result == "partially_correct": return "KNOWLEDGE_GAP"
    if result == "incorrect" and misconception: return "MISCONCEPTION"
    if result == "incorrect" and step_type in {"problem", "worked_step", "numeric", "ordering"}: return "PROCEDURAL_ERROR"
    if result == "incorrect" and attempts <= 1: return "UNCERTAINTY"
    return "KNOWLEDGE_GAP"

def _strategy_for(step, concept: dict, revisit: bool, remediation: str | None) -> str:
    if revisit: return "DELAYED_RECHECK"
    if remediation == "prerequisite": return "PREREQUISITE_REPAIR"
    if concept.get("state") in {"STRUGGLING", "NEEDS_REVIEW"}: return "ERROR_CORRECTION"
    return {"teach": "CONCEPTUAL_EXPLANATION", "walkthrough": "ANIMATED_MECHANISM", "problem": "SCAFFOLDED_PRACTICE", "worked_step": "SCAFFOLDED_PRACTICE", "numeric": "TRANSFER_PRACTICE", "multiple_choice": "RETRIEVAL_PRACTICE", "short_answer": "SOCRATIC_PROBE", "teach_back": "TRANSFER_PRACTICE", "prediction": "GUIDED_DISCOVERY", "ordering": "GUIDED_DISCOVERY", "matching": "CONTRAST_CASE", "labeling": "VISUAL_MODEL", "fill_blank": "RETRIEVAL_PRACTICE"}.get(step.type, "DIRECT_INSTRUCTION")

def _action_for(step, objective: dict, concept: dict, revisit: bool = False, remediation: str | None = None) -> TutorAction:
    mapping = {"teach": "teach_concept", "multiple_choice": "ask_multiple_choice", "short_answer": "ask_free_response", "numeric": "ask_free_response", "prediction": "ask_prediction", "ordering": "ask_ordering", "matching": "ask_matching", "labeling": "ask_labeling", "fill_blank": "ask_fill_blank", "worked_step": "ask_worked_step", "teach_back": "ask_teach_back", "problem": "ask_free_response", "walkthrough": "show_process_visual"}
    remediation_map = {"simplify": "decrease_difficulty", "example": "give_example", "prerequisite": "revisit_prerequisite", "change_modality": "give_analogy", "revisit": "revisit_concept"}
    action_type = remediation_map.get(remediation or "") or ("revisit_concept" if revisit else mapping.get(step.type, "teach_concept"))
    if concept.get("state") in {"STRUGGLING", "NEEDS_REVIEW"} and not revisit and step.type not in {"teach", "walkthrough"}:
        # Keep remediation explicit while preserving the current interaction's
        # stable contract; the runtime chooses the alternate validated step.
        action_type = remediation_map.get(remediation or "") or "clarify_definition"
    used = set(concept.get("interactionTypes") or [])
    if step.type == "multiple_choice" and "multiple_choice" in used and not revisit:
        action_type = "ask_free_response"
    rationale = "Revisit with a different validated modality after earlier evidence." if revisit else "A bounded action selected for the learner's current evidence and goal."
    return TutorAction(id=f"action-{step.id}", type=action_type, conceptId=objective.get("id", "concept"), stepId=step.id, rationale=rationale, strategy=_strategy_for(step, concept, revisit, remediation))

def _report(session: LearnSession) -> LearnSessionReport:
    objectives = session.plan.get("objectives", []); by_id = {item.get("conceptId"): item for item in _concepts(session)}
    covered, demonstrated, developing, struggles, needs_review, not_covered, misconceptions = [], [], [], [], [], [], []
    for objective in objectives:
        item = by_id.get(objective.get("id"), {}); state = item.get("state", "NOT_SEEN"); title = objective.get("title", "Concept")
        if state == "NOT_SEEN": not_covered.append(title)
        else: covered.append(title)
        if state == "DEMONSTRATED": demonstrated.append(title)
        elif state in {"DEVELOPING", "INTRODUCED"}: developing.append(title)
        if state == "STRUGGLING": struggles.append(f"{title}: " + (item.get("misconceptions") or ["understanding is not yet consistent"])[-1])
        misconceptions.extend(item.get("misconceptions") or [])
        if state in {"NEEDS_REVIEW", "STRUGGLING"}: needs_review.append(title)
    queue = list((session.state or {}).get("revisitQueue") or []); next_focus = [by_id.get(cid, {}).get("title", cid) for cid in queue]
    next_focus.extend(needs_review)
    return LearnSessionReport(covered=covered, demonstrated=demonstrated, developing=developing, struggles=struggles, misconceptions=list(dict.fromkeys(misconceptions)), needsReview=list(dict.fromkeys(needs_review)), notCovered=not_covered, nextFocus=list(dict.fromkeys(next_focus)), stopped=session.status == "stopped")

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

def _ask_scope(message: str, objective: dict, context: dict) -> str:
    terms = set(re.findall(r"[a-z0-9]{3,}", message.lower()))
    concept_terms = set(re.findall(r"[a-z0-9]{3,}", (objective.get("title", "") + " " + objective.get("outcome", "")).lower()))
    source_terms = set(re.findall(r"[a-z0-9]{3,}", context.get("text", "").lower()))
    if terms & (concept_terms | source_terms): return "IN_SCOPE_SOURCE"
    if any(word in message.lower() for word in ("why", "how", "what does", "formula", "prerequisite", "mean")):
        return "IN_SCOPE_PREREQUISITE"
    return "OUT_OF_SCOPE"

def _record_tutor_event(db, *, user_id, session_id, document_id, event_type: str, metadata: dict) -> None:
    try:
        db.add(LearnTutorEvent(user_id=user_id, session_id=session_id, document_id=document_id, event_type=event_type, event_metadata=metadata))
        db.flush()
    except Exception:
        db.rollback()

def _ask_rate_allowed(db, user_id, session_id) -> bool:
    now = datetime.now(timezone.utc); key = str(user_id); recent = [stamp for stamp in _ASK_RATE.get(key, []) if time.monotonic() - stamp < _ASK_WINDOW_SECONDS]
    try:
        durable = db.execute(select(LearnTutorEvent).where(LearnTutorEvent.user_id == user_id, LearnTutorEvent.event_type == "ask_request", LearnTutorEvent.created_at >= now.replace(tzinfo=None))).scalars().all()
        if len(durable) >= _ASK_MAX_REQUESTS: return False
    except Exception:
        pass
    if len(recent) >= _ASK_MAX_REQUESTS: return False
    recent.append(time.monotonic()); _ASK_RATE[key] = recent
    return True

@router.post("/learn-sessions/{session_id}/ask", response_model=AskLucentResponse, dependencies=[Depends(require_csrf)])
def ask_lucent(session_id: UUID, request: AskLucentRequest, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if not _ask_rate_allowed(db, user.id, session.id):
        _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="rate_limit", metadata={"scope": "ask"}); db.commit()
        raise HTTPException(status_code=429, detail="Ask Lucent is taking a short pause. Try again in a moment.")
    objectives = session.plan.get("objectives", []); objective = objectives[min(session.objective_index, max(0, len(objectives) - 1))] if objectives else {}
    note = _latest_note(db, session.document_id); payload = {}
    if note:
        try: payload = json.loads(note.content)
        except (TypeError, ValueError): payload = {}
    context = retrieve_note_context(payload, f"{objective.get('title', '')} {request.message}")
    scope = _ask_scope(request.message, objective, context)
    _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="ask_request", metadata={"scope": scope, "sourceSectionIds": context.get("sourceSectionIds", [])})
    if scope == "OUT_OF_SCOPE":
        _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="ask_refusal", metadata={"scope": scope}); db.commit()
        return AskLucentResponse(answer="I can help with the material you’re currently learning and related prerequisite concepts.", scope=scope)
    current_step = _parse_step(objective.get("steps", [])[session.step_index]) if objective.get("steps") and session.step_index < len(objective.get("steps", [])) else None
    tool = "retrieve_source" if context.get("text") else "request_explanation"
    visual_action = None
    lowered = request.message.lower()
    if current_step and getattr(current_step, "visual_spec", None) and any(word in lowered for word in ("show", "visual", "diagram", "stage", "highlight")):
        tool = "show_visual"; visual_action = {"type": "show_visual", "stepId": current_step.id, "stage": 0}
    learner = _concept_for(session, objective)
    model = ask_lucent_model(question=request.message, context={"policy": "Use only bounded allowlisted tools. Do not mutate learner state.", "learner": json.dumps({"goal": session.goal, "familiarity": session.familiarity, "recent": learner.get("lastResult"), "hints": learner.get("hintsUsed", 0)}), "concept": json.dumps({"title": objective.get("title"), "outcome": objective.get("outcome"), "misconceptions": learner.get("misconceptions", [])}), "source": context.get("text", "")})
    if model:
        answer = model.answer; tool = "request_explanation"; visual_action = None
        for call in model.tool_calls:
            args = call.arguments
            allowed_keys = {"stage"} if call.tool == "change_visual_stage" else {"nodeId"} if call.tool == "highlight_visual_element" else set()
            if set(args) - allowed_keys:
                _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="validation_failure", metadata={"tool": call.tool, "reason": "unknown_arguments"}); continue
            if call.tool in {"show_visual", "change_visual_stage"} and current_step and getattr(current_step, "visual_spec", None):
                stages = getattr(current_step.visual_spec, "stages", [])
                stage = int(args.get("stage", 0)) if str(args.get("stage", 0)).isdigit() else 0
                if 0 <= stage < len(stages): tool = call.tool; visual_action = {"type": call.tool, "stepId": current_step.id, "stage": stage}; break
                _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="validation_failure", metadata={"tool": call.tool, "reason": "stage_out_of_range"}); continue
            if call.tool == "highlight_visual_element" and current_step and getattr(current_step, "visual_spec", None):
                node_id = str(args.get("nodeId", "")); valid_ids = {node.id for node in current_step.visual_spec.nodes}
                if node_id in valid_ids:
                    tool = call.tool; visual_action = {"type": call.tool, "stepId": current_step.id, "nodeId": node_id}; break
                _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="validation_failure", metadata={"tool": call.tool, "reason": "unknown_visual_node"}); continue
            if call.tool in {"retrieve_source", "request_example", "request_explanation"}: tool = call.tool
        _record_tutor_event(db, user_id=user.id, session_id=session.id, document_id=session.document_id, event_type="ask_model", metadata={"scope": scope, "tool": tool, "sourceSectionIds": model.source_section_ids, "sourceBlockIds": model.source_block_ids})
    else:
        answer = context.get("text") or "I can explain the current concept, but the saved notes do not contain enough detail to support a grounded answer yet."
    if scope == "IN_SCOPE_PREREQUISITE": answer = "This is a related prerequisite. The saved material does not fully explain it, so treat this as supporting context rather than a claim from the source.\n\n" + answer
    db.commit(); return AskLucentResponse(answer=answer[:1800], scope=scope, sourceSectionIds=context.get("sourceSectionIds", []), sourceBlockIds=context.get("sourceBlockIds", []), tool=tool, visualAction=visual_action)

def _initial_state(db, user: User, document_id: int, plan: dict) -> dict:
    prior = db.execute(select(LearnSession).where(LearnSession.user_id == user.id, LearnSession.document_id == document_id).order_by(LearnSession.updated_at.desc())).scalars().first()
    prior_map = {c.get("conceptId"): c for c in ((prior.state or {}).get("concepts") if prior else [])}; concepts = []
    for objective in plan.get("objectives", []):
        previous = dict(prior_map.get(objective.get("id"), {})); concepts.append({"conceptId": objective.get("id"), "title": objective.get("title", "Concept"), "state": previous.get("state", "NOT_SEEN"), "attempts": 0, "correct": 0, "partiallyCorrect": 0, "incorrect": 0, "insufficientEvidence": 0, "hintsUsed": 0, "interactionTypes": [], "misconceptions": previous.get("misconceptions", []), "failedStrategies": previous.get("failedStrategies", []), "successfulStrategies": previous.get("successfulStrategies", []), "failedModalities": previous.get("failedModalities", []), "successfulModalities": previous.get("successfulModalities", []), "recognitionEvidence": previous.get("recognitionEvidence", 0), "recallEvidence": previous.get("recallEvidence", 0), "explanationEvidence": previous.get("explanationEvidence", 0), "applicationEvidence": previous.get("applicationEvidence", 0), "transferEvidence": previous.get("transferEvidence", 0), "scaffoldingLevel": previous.get("scaffoldingLevel", 0), "reviewDue": previous.get("reviewDue", None), "immediateSuccess": False, "delayedSuccess": False, "sourceSectionIds": objective.get("sourceSectionIds", []), "sourceBlockIds": objective.get("sourceBlockIds", []), "priorEvidence": previous.get("correct", 0), "lastResult": None})
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

def _choose_next_step(objective: dict, current_index: int, state: dict, concept: dict, *, failed: bool = False) -> int | None:
    """Choose the next validated teaching/checking action from evidence.

    The persisted plan is a bounded vocabulary of candidate actions, not a
    script. Prefer unseen modalities after failure and avoid repeating a
    modality that already failed unless there is no safe alternative.
    """
    steps = objective.get("steps", [])
    used = set(concept.get("interactionTypes") or [])
    attempts = state.get("attempts") or {}
    candidates: list[tuple[int, object]] = []
    for index in range(current_index + 1, len(steps)):
        parsed = _parse_step(steps[index])
        if not parsed or parsed.type in {"teach", "walkthrough"}:
            continue
        if int(attempts.get(parsed.id, 0)) == 0:
            candidates.append((index, parsed))
    if failed:
        fresh = [item for item in candidates if item[1].type not in used]
        if fresh:
            return fresh[0][0]
    if candidates:
        return candidates[0][0]
    return None

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

def _append_prerequisite_branch(session: LearnSession, objective: dict, failed_step) -> int:
    plan = deepcopy(session.plan); target = next(item for item in plan["objectives"] if item.get("id") == objective.get("id")); steps = target.setdefault("steps", [])
    branch_id = f"{failed_step.id}-prerequisite-{len(steps)}"
    branch = ShortAnswerStep(id=branch_id, type="short_answer", title="Repair the prerequisite", prompt="What basic relationship must be true before this step can work?", acceptedAnswers=[failed_step.feedback_incorrect or "the defining relationship"], requiredConcepts=[], hints=["Name the relationship the current step depends on."], feedbackIncorrect="We will revisit this prerequisite before returning to the main idea.", sourceSectionIds=failed_step.source_section_ids, sourceBlockIds=failed_step.source_block_ids)
    steps.append(branch.model_dump(by_alias=True)); session.plan = plan
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
        note = _latest_note(db, session.document_id); context = ""
        if note:
            try: context = retrieve_note_context(json.loads(note.content), getattr(step, "prompt", "")).get("text", "")
            except (TypeError, ValueError): context = ""
        evaluation = diagnose_response(prompt=getattr(step, "prompt", ""), expected=expected, response=request.response, source_context=context or " ".join(objective.get("sourceSectionIds", [])), fallback=evaluation)
    concepts = [dict(c) for c in state.get("concepts", [])]; concept = next((c for c in concepts if c.get("conceptId") == objective["id"]), _concept_for(session, objective)); concept["attempts"] = int(concept.get("attempts", 0)) + (0 if evaluation.result == "insufficient_evidence" else 1); concept["lastSeen"] = _now(); concept["lastResult"] = evaluation.result
    state["lastRemediation"] = evaluation.remediation_category if evaluation.result in {"incorrect", "partially_correct"} else None
    concept["diagnosisType"] = _diagnosis_type(evaluation.result, step.type, attempt_number, evaluation.misconception)
    concept["reviewDue"] = "later_this_session" if evaluation.result in {"incorrect", "partially_correct"} else concept.get("reviewDue")
    if step.type in {"multiple_choice", "prediction", "matching", "labeling"}: concept["recognitionEvidence"] = int(concept.get("recognitionEvidence", 0)) + (1 if evaluation.result == "correct" else 0)
    if step.type in {"short_answer", "fill_blank"}: concept["recallEvidence"] = int(concept.get("recallEvidence", 0)) + (1 if evaluation.result == "correct" else 0)
    if step.type in {"teach_back", "short_answer"}: concept["explanationEvidence"] = int(concept.get("explanationEvidence", 0)) + (1 if evaluation.result == "correct" else 0)
    if step.type in {"problem", "worked_step", "numeric", "ordering"}: concept["applicationEvidence"] = int(concept.get("applicationEvidence", 0)) + (1 if evaluation.result == "correct" else 0)
    if step.type in {"prediction", "problem", "teach_back"} and evaluation.result == "correct" and int((state.get("hints") or {}).get(step.id, 0)) == 0: concept["transferEvidence"] = int(concept.get("transferEvidence", 0)) + 1
    concept["scaffoldingLevel"] = max(0, int(concept.get("scaffoldingLevel", 0)) - 1) if evaluation.result == "correct" else min(3, int(concept.get("scaffoldingLevel", 0)) + 1)
    concept.setdefault("firstSeen", concept["lastSeen"])
    if step.type not in {"teach", "walkthrough"} and step.type not in concept.get("interactionTypes", []): concept.setdefault("interactionTypes", []).append(step.type)
    if evaluation.result == "correct": concept["correct"] = int(concept.get("correct", 0)) + 1; concept["immediateSuccess"] = True; concept["state"] = "DEMONSTRATED" if concept.get("delayedSuccess") or concept.get("priorEvidence", 0) else "DEVELOPING"
    elif evaluation.result == "partially_correct": concept["partiallyCorrect"] = int(concept.get("partiallyCorrect", 0)) + 1; concept["state"] = "DEVELOPING"
    elif evaluation.result == "incorrect":
        concept["incorrect"] = int(concept.get("incorrect", 0)) + 1; concept["state"] = "STRUGGLING" if concept["incorrect"] >= 2 else "DEVELOPING"; misconception = evaluation.misconception
        if misconception and misconception not in concept.setdefault("misconceptions", []): concept["misconceptions"].append(misconception)
    else: concept["insufficientEvidence"] = int(concept.get("insufficientEvidence", 0)) + 1; concept["state"] = "INTRODUCED"
    strategy = "RETRIEVAL_PRACTICE" if step.type in {"multiple_choice", "short_answer", "fill_blank"} else "SCAFFOLDED_PRACTICE" if step.type in {"problem", "worked_step", "numeric"} else "GUIDED_DISCOVERY"
    bucket = "successfulStrategies" if evaluation.result == "correct" else "failedStrategies" if evaluation.result in {"incorrect", "partially_correct"} else None
    if bucket and strategy not in concept.setdefault(bucket, []): concept[bucket].append(strategy)
    modality_bucket = "successfulModalities" if evaluation.result == "correct" else "failedModalities" if evaluation.result in {"incorrect", "partially_correct"} else None
    if modality_bucket and step.type not in concept.setdefault(modality_bucket, []): concept[modality_bucket].append(step.type)
    state["concepts"] = [concept if c.get("conceptId") == objective["id"] else c for c in concepts]
    db.add(LearnAttempt(session_id=session.id, objective_id=objective["id"], step_id=step.id, step_type=step.type, response=request.response or request.option_id or (",".join(request.ordered_ids or [])), result=evaluation.result, attempt_number=attempt_number, hints_used=int((state.get("hints") or {}).get(step.id, 0)), evaluation=evaluation.model_dump(by_alias=True)))
    feedback = step.feedback_correct if evaluation.result == "correct" else step.feedback_incorrect or evaluation.misconception or evaluation.evidence
    if evaluation.result in {"incorrect", "partially_correct"}:
        queue = list(state.get("revisitQueue") or []); state["revisitQueue"] = queue if objective["id"] in queue else queue + [objective["id"]]
    elif objective["id"] in state.get("revisitQueue", []) and state.get("revisitMode"):
        state["revisitQueue"] = [cid for cid in state["revisitQueue"] if cid != objective["id"]]; concept["delayedSuccess"] = True; concept["state"] = "DEMONSTRATED"; state["revisitMode"] = False
    session.state = state
    if evaluation.result in {"incorrect", "partially_correct"}:
        next_idx = _choose_next_step(objective, session.step_index, state, concept, failed=True)
        if next_idx is None and evaluation.result == "incorrect" and int(concept.get("incorrect", 0)) >= 2 and not state.get("prerequisiteBranch"):
            return_step = session.step_index
            branch_index = _append_prerequisite_branch(session, objective, step)
            state["prerequisiteBranch"] = {"conceptId": objective["id"], "returnStep": return_step, "branchIndex": branch_index}
            session.step_index = branch_index
        else:
            session.step_index = next_idx if next_idx is not None else _append_remediation(session, objective, step)
    else:
        next_idx = _choose_next_step(objective, session.step_index, state, concept)
        session.step_index = next_idx if next_idx is not None else session.step_index + 1
    if state.get("prerequisiteBranch") and evaluation.result == "correct" and session.step_index == int(state["prerequisiteBranch"].get("branchIndex", -1)):
        session.step_index = int(state["prerequisiteBranch"].get("returnStep", session.step_index))
        state["prerequisiteBranch"] = None
    current_steps = session.plan.get("objectives", [])[session.objective_index].get("steps", []) if session.objective_index < len(session.plan.get("objectives", [])) else []
    if session.step_index >= len(current_steps): _next_objective(session, state)
    if _completion_met(session): session.status = "completed"; session.ended_reason = "evidence_sufficient"; session.report = _report(session).model_dump(by_alias=True)
    db.commit(); return _session_payload(session, feedback=feedback, feedback_kind="correct" if evaluation.result == "correct" else "incorrect" if evaluation.result in {"incorrect", "partially_correct"} else "info", evaluation=evaluation)

@router.post("/learn-sessions/{session_id}/stop", response_model=LearnSessionResponse, dependencies=[Depends(require_csrf)])
def stop_learn_session(session_id: UUID, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if session.status == "active": session.status = "stopped"; session.ended_reason = "user_stopped"; session.report = _report(session).model_dump(by_alias=True); db.commit()
    return _session_payload(session)
