import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.database import get_db
from app.models.document import Document
from app.models.source import Source
from app.models.auth import User
from app.auth_dependencies import get_current_user, require_csrf
from app.models.quiz import Quiz, QuizAttempt
from app.models.note import Note
from app.schemas.quiz import QuizResponse, QuizAttemptCreateRequest, QuizAttemptResponse
from app.services.anthropic_service import generate_quiz_questions

router = APIRouter()


def _note_quiz_source(note: Note) -> tuple[str, list[str]] | None:
    if note.content_type != "section_note":
        return None
    try:
        payload = json.loads(note.content)
        sections = payload.get("sectionNotes", [])
    except (TypeError, ValueError, AttributeError):
        return None
    chunks, section_ids = [], []
    for section in sections:
        section_id = section.get("id")
        if not isinstance(section_id, str):
            continue
        section_ids.append(section_id)
        component_text = []
        for component in section.get("components", []):
            for key in ("text", "definition", "takeaway", "equation", "result", "interpretation"):
                value = component.get(key)
                if isinstance(value, str) and value.strip():
                    component_text.append(value.strip())
        chunks.append(
            f"[section:{section_id}] {section.get('title', '')}\n"
            f"{section.get('bigIdea', '')}\n"
            f"{' '.join(component_text)}\n"
            f"Takeaways: {'; '.join(section.get('keyTakeaways', []))}"
        )
    return ("\n\n".join(chunks), section_ids) if chunks else None


def _associate_question(question, section_ids: list[str], section_source: str):
    if question.section_id in section_ids:
        return question
    # A deterministic lexical association keeps review navigation useful when
    # the provider omits or mistypes a marker; it does not change quiz content.
    terms = set(re.findall(r"[a-z0-9]{3,}", f"{question.question} {question.explanation}".lower()))
    chunks = section_source.split("\n\n")
    best_id, best_score = None, -1
    for section_id, chunk in zip(section_ids, chunks):
        score = len(terms & set(re.findall(r"[a-z0-9]{3,}", chunk.lower())))
        if score > best_score:
            best_id, best_score = section_id, score
    return question.model_copy(update={"section_id": best_id})

@router.post("/documents/{document_id}/quizzes", response_model=QuizResponse, dependencies=[Depends(require_csrf)])
def create_quiz(document_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    note = db.execute(select(Note).where(
        Note.document_id == document.id,
        Note.content_type == "section_note",
    ).order_by(Note.updated_at.desc())).scalars().first()
    note_source = _note_quiz_source(note) if note else None
    quiz_content, section_ids = note_source if note_source else (document.content, [])
    try:
        generated = generate_quiz_questions(document.title, quiz_content, section_ids=section_ids)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    quiz = Quiz(
        document_id=document.id,
        title=f"Quiz: {document.title}",
        questions=[_associate_question(q, section_ids, quiz_content).model_dump() for q in generated.questions]
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz

@router.get("/documents/{document_id}/quizzes", response_model=list[QuizResponse])
def get_quizzes_for_document(document_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(Quiz).join(Document).join(Source).where(Quiz.document_id == document_id, Source.user_id == user.id)
    result = db.execute(statement)
    return result.scalars().all()

@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
def get_quiz(quiz_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    quiz = db.execute(select(Quiz).join(Document).join(Source).where(Quiz.id == quiz_id, Source.user_id == user.id)).scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz

@router.post("/quizzes/{quiz_id}/attempts", response_model=QuizAttemptResponse, dependencies=[Depends(require_csrf)])
def create_quiz_attempt(quiz_id: int, attempt_request: QuizAttemptCreateRequest, db = Depends(get_db), user: User = Depends(get_current_user)):
    quiz = db.execute(select(Quiz).join(Document).join(Source).where(Quiz.id == quiz_id, Source.user_id == user.id)).scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    attempt = QuizAttempt(
        user_id=user.id,
        quiz_id=quiz_id,
        score=attempt_request.score,
        total=attempt_request.total
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/quiz-attempts/{attempt_id}", response_model=QuizAttemptResponse)
def get_quiz_attempt(attempt_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.execute(
        select(QuizAttempt)
        .join(Quiz).join(Document).join(Source)
        .where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user.id, Source.user_id == user.id)
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    return attempt
