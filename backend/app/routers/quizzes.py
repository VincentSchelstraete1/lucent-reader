from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.database import get_db
from app.models.document import Document
from app.models.quiz import Quiz, QuizAttempt
from app.schemas.quiz import QuizResponse, QuizAttemptCreateRequest, QuizAttemptResponse
from app.services.anthropic_service import generate_quiz_questions

router = APIRouter()

@router.post("/documents/{document_id}/quizzes", response_model=QuizResponse)
def create_quiz(document_id: int, db = Depends(get_db)):
    document = db.get(Document, document_id)
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
def get_quizzes_for_document(document_id: int, db = Depends(get_db)):
    statement = select(Quiz).where(Quiz.document_id == document_id)
    result = db.execute(statement)
    return result.scalars().all()

@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
def get_quiz(quiz_id: int, db = Depends(get_db)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz

@router.post("/quizzes/{quiz_id}/attempts", response_model=QuizAttemptResponse)
def create_quiz_attempt(quiz_id: int, attempt_request: QuizAttemptCreateRequest, db = Depends(get_db)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        score=attempt_request.score,
        total=attempt_request.total
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt
