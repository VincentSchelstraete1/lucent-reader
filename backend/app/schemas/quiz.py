from pydantic import BaseModel, Field, model_validator
from datetime import datetime

class QuizQuestion(BaseModel):
    question: str
    choices: list[str] = Field(min_length=2, max_length=4)
    correct_index: int
    explanation: str
    section_id: str | None = None

    @model_validator(mode="after")
    def correct_answer_exists(self):
        if not 0 <= self.correct_index < len(self.choices):
            raise ValueError("correct_index must reference an answer choice")
        return self

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
