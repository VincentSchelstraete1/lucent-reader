from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.database import get_db
from app.models.document import Document
from app.models.source import Source
from app.models.auth import User
from app.auth_dependencies import get_current_user, require_csrf
from app.models.quiz import Quiz, QuizAttempt
from app.schemas.quiz import QuizResponse, QuizAttemptCreateRequest, QuizAttemptResponse
from app.services.anthropic_service import generate_quiz_questions

router = APIRouter()

@router.post("/documents/{document_id}/quizzes", response_model=QuizResponse, dependencies=[Depends(require_csrf)])
def create_quiz(document_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        generated = generate_quiz_questions(document.title, document.content)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    quiz = Quiz(
        document_id=document.id,
        title=f"Quiz: {document.title}",
        questions=[q.model_dump() for q in generated.questions]
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
