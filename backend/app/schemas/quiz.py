from pydantic import BaseModel
from datetime import datetime

class QuizQuestion(BaseModel):
    question: str
    choices: list[str]
    correct_index: int
    explanation: str

class GeneratedQuizQuestions(BaseModel):
    questions: list[QuizQuestion]

class QuizResponse(BaseModel):
    id: int
    document_id: int
    title: str
    questions: list[QuizQuestion]
    created_at: datetime

    model_config = {"from_attributes": True}

class QuizAttemptCreateRequest(BaseModel):
    score: int
    total: int

class QuizAttemptResponse(BaseModel):
    id: int
    quiz_id: int
    score: int
    total: int
    created_at: datetime

    model_config = {"from_attributes": True}
