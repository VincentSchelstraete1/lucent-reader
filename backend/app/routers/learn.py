from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.auth_dependencies import get_current_user, require_csrf
from app.database import get_db
from app.models.auth import User
from app.models.document import Document
from app.models.learn import LearnAttempt, LearnSession
from app.models.note import Note
from app.models.source import Source
from app.schemas.learn import LearnHintResponse, LearnResponseRequest, LearnSessionCreateRequest, LearnSessionResponse
from app.services.learn_engine import build_learn_plan, grade_step, plan_fingerprint, public_step

router = APIRouter()


def _owned_document(db, document_id: int, user: User) -> Document:
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Study material not found")
    return document


def _latest_note(db, document_id: int) -> Note | None:
    return db.execute(select(Note).where(Note.document_id == document_id, Note.content_type == "section_note").order_by(Note.updated_at.desc())).scalars().first()


def _session_payload(session: LearnSession, *, feedback: str | None = None, feedback_kind: str | None = None) -> LearnSessionResponse:
    plan = session.plan
    objectives = plan.get("objectives", [])
    state = session.state or {}
    current = None
    objective_title = None
    if session.status == "active" and session.objective_index < len(objectives):
        objective = objectives[session.objective_index]
        objective_title = objective.get("title")
        steps = objective.get("steps", [])
        if session.step_index < len(steps):
            # The persisted plan was validated before it was stored. Re-validate
            # the current item at the boundary so corrupted state cannot reach UI.
            from pydantic import TypeAdapter
            from app.schemas.learn import LearnStep as LearnStepType
            try:
                parsed = TypeAdapter(LearnStepType).validate_python(steps[session.step_index])
                hints_used = int((state.get("hints") or {}).get(parsed.id, 0))
                current = public_step(parsed, hints_used)
            except Exception:
                current = None
    completed = len(state.get("completed", []))
    return LearnSessionResponse(id=str(session.id), documentId=session.document_id, goal=session.goal, familiarity=session.familiarity, status=session.status, objectiveIndex=session.objective_index, stepIndex=session.step_index, objectiveCount=len(objectives), objectiveTitle=objective_title, step=current, feedback=feedback, feedbackKind=feedback_kind, hintsUsed=int((state.get("hints") or {}).get(current.id, 0)) if current else 0, completedObjectives=completed, weakObjectives=list(state.get("weak", [])))


def _get_owned_session(db, session_id: UUID, user: User) -> LearnSession:
    session = db.execute(select(LearnSession).where(LearnSession.id == session_id, LearnSession.user_id == user.id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Learning session not found")
    return session


@router.post("/documents/{document_id}/learn-sessions", response_model=LearnSessionResponse, dependencies=[Depends(require_csrf)])
def create_learn_session(document_id: int, request: LearnSessionCreateRequest, db=Depends(get_db), user: User = Depends(get_current_user)):
    document = _owned_document(db, document_id, user)
    note = _latest_note(db, document_id)
    if not note:
        raise HTTPException(status_code=409, detail="Create notes for this material before starting Learn")
    try:
        payload = json.loads(note.content)
    except (TypeError, ValueError):
        raise HTTPException(status_code=409, detail="The notes for this material are unavailable")
    fingerprint = plan_fingerprint(payload, request.goal, request.familiarity)
    if not request.restart:
        existing = db.execute(select(LearnSession).where(LearnSession.user_id == user.id, LearnSession.document_id == document.id, LearnSession.plan_fingerprint == fingerprint, LearnSession.status == "active").order_by(LearnSession.updated_at.desc())).scalars().first()
        if existing:
            return _session_payload(existing)
    plan = build_learn_plan(payload, request.goal, request.familiarity)
    session = LearnSession(user_id=user.id, document_id=document.id, note_id=note.id, goal=request.goal, familiarity=request.familiarity, plan=plan.model_dump(by_alias=True), objective_index=0, step_index=0, state={"attempts": {}, "hints": {}, "weak": [], "completed": []}, status="active", plan_fingerprint=fingerprint)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_payload(session)


@router.get("/learn-sessions/{session_id}", response_model=LearnSessionResponse)
def get_learn_session(session_id: UUID, db=Depends(get_db), user: User = Depends(get_current_user)):
    return _session_payload(_get_owned_session(db, session_id, user))


@router.get("/documents/{document_id}/learn-sessions/active", response_model=LearnSessionResponse | None)
def get_active_learn_session(document_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    _owned_document(db, document_id, user)
    session = db.execute(select(LearnSession).where(LearnSession.document_id == document_id, LearnSession.user_id == user.id, LearnSession.status == "active").order_by(LearnSession.updated_at.desc())).scalars().first()
    return _session_payload(session) if session else None


@router.post("/learn-sessions/{session_id}/hints", response_model=LearnHintResponse, dependencies=[Depends(require_csrf)])
def get_learn_hint(session_id: UUID, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="This learning session is no longer active")
    objective = session.plan["objectives"][session.objective_index]
    step = objective["steps"][session.step_index]
    from pydantic import TypeAdapter
    from app.schemas.learn import LearnStep as LearnStepType
    parsed = TypeAdapter(LearnStepType).validate_python(step)
    state = dict(session.state or {})
    hints = dict(state.get("hints") or {})
    used = int(hints.get(parsed.id, 0))
    if used >= len(parsed.hints):
        raise HTTPException(status_code=409, detail="No more hints are available")
    hints[parsed.id] = used + 1
    state["hints"] = hints
    session.state = state
    db.commit()
    return LearnHintResponse(hint=parsed.hints[used], hintsUsed=used + 1)


@router.post("/learn-sessions/{session_id}/responses", response_model=LearnSessionResponse, dependencies=[Depends(require_csrf)])
def submit_learn_response(session_id: UUID, request: LearnResponseRequest, db=Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user)
    if session.status != "active":
        return _session_payload(session, feedback="This session is complete.", feedback_kind="info")
    objective = session.plan["objectives"][session.objective_index]
    raw_step = objective["steps"][session.step_index]
    from pydantic import TypeAdapter
    from app.schemas.learn import LearnStep as LearnStepType
    try:
        step = TypeAdapter(LearnStepType).validate_python(raw_step)
    except Exception:
        # A bad persisted item is isolated and skipped rather than breaking the session.
        session.step_index += 1
        db.commit()
        return _advance_if_needed(session, db)
    state = dict(session.state or {})
    attempts = dict(state.get("attempts") or {})
    attempt_number = int(attempts.get(step.id, 0)) + 1
    attempts[step.id] = attempt_number
    state["attempts"] = attempts
    correct, feedback = grade_step(step, response=request.response, option_id=request.option_id)
    result = "info" if correct is None else "correct" if correct else "incorrect"
    db.add(LearnAttempt(session_id=session.id, objective_id=objective["id"], step_id=step.id, step_type=step.type, response=request.response or request.option_id, result=result, attempt_number=attempt_number, hints_used=int((state.get("hints") or {}).get(step.id, 0))))
    if correct is False and attempt_number < 2:
        session.state = state
        db.commit()
        return _session_payload(session, feedback=feedback, feedback_kind="incorrect")
    if correct is False:
        weak = list(state.get("weak", []))
        if objective["id"] not in weak:
            weak.append(objective["id"])
        state["weak"] = weak
    session.state = state
    session.step_index += 1
    db.commit()
    response_payload = _advance_if_needed(session, db)
    response_payload.feedback = feedback
    response_payload.feedback_kind = "correct" if correct else "incorrect" if correct is False else "info"
    return response_payload


def _advance_if_needed(session: LearnSession, db) -> LearnSessionResponse:
    objectives = session.plan.get("objectives", [])
    state = dict(session.state or {})
    while session.objective_index < len(objectives) and session.step_index >= len(objectives[session.objective_index].get("steps", [])):
        completed = list(state.get("completed", []))
        objective_id = objectives[session.objective_index]["id"]
        if objective_id not in state.get("weak", []) and objective_id not in completed:
            completed.append(objective_id)
        state["completed"] = completed
        session.objective_index += 1
        session.step_index = 0
    if session.objective_index >= len(objectives):
        session.status = "completed"
    session.state = state
    db.commit()
    return _session_payload(session)
