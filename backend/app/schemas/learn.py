from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


LearnGoal = Literal["understand", "solve", "memorize", "exam"]
Familiarity = Literal["new", "somewhat_familiar", "reviewing"]
LearnStatus = Literal["active", "completed", "abandoned"]


class LearnOption(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=160)


class LearnStepBase(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    feedback_correct: str | None = Field(default=None, alias="feedbackCorrect", max_length=500)
    feedback_incorrect: str | None = Field(default=None, alias="feedbackIncorrect", max_length=500)
    hints: list[str] = Field(default_factory=list, max_length=3)
    remediation: str | None = Field(default=None, max_length=500)


class TeachStep(LearnStepBase):
    type: Literal["teach"]
    content: str = Field(min_length=1, max_length=900)
    visual_ref: dict | None = Field(default=None, alias="visualRef")


class MultipleChoiceStep(LearnStepBase):
    type: Literal["multiple_choice"]
    prompt: str = Field(min_length=1, max_length=500)
    options: list[LearnOption] = Field(min_length=2, max_length=5)
    answer_id: str = Field(alias="answerId", min_length=1, max_length=40)

    @model_validator(mode="after")
    def answer_exists(self):
        if self.answer_id not in {option.id for option in self.options}:
            raise ValueError("answerId must reference an option")
        return self


class ShortAnswerStep(LearnStepBase):
    type: Literal["short_answer"]
    prompt: str = Field(min_length=1, max_length=500)
    accepted_answers: list[str] = Field(alias="acceptedAnswers", min_length=1, max_length=8)
    required_concepts: list[str] = Field(default_factory=list, alias="requiredConcepts", max_length=6)


class NumericAnswerStep(LearnStepBase):
    type: Literal["numeric"]
    prompt: str = Field(min_length=1, max_length=500)
    answer: float
    tolerance: float = Field(default=0.01, ge=0, le=1000000)
    unit: str | None = Field(default=None, max_length=30)


class PredictionStep(LearnStepBase):
    type: Literal["prediction"]
    prompt: str = Field(min_length=1, max_length=500)
    options: list[LearnOption] = Field(min_length=2, max_length=5)
    answer_id: str = Field(alias="answerId", min_length=1, max_length=40)
    reveal: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def answer_exists(self):
        if self.answer_id not in {option.id for option in self.options}:
            raise ValueError("answerId must reference an option")
        return self


class ProblemStep(LearnStepBase):
    type: Literal["problem"]
    prompt: str = Field(min_length=1, max_length=500)
    response_type: Literal["short_answer", "numeric"] = Field(alias="responseType")
    accepted_answers: list[str] = Field(default_factory=list, alias="acceptedAnswers", max_length=8)
    answer: float | None = None
    tolerance: float | None = Field(default=None, ge=0, le=1000000)
    solution: str = Field(min_length=1, max_length=700)

    @model_validator(mode="after")
    def response_contract(self):
        if self.response_type == "numeric" and self.answer is None:
            raise ValueError("numeric problem steps require an answer")
        if self.response_type == "short_answer" and not self.accepted_answers:
            raise ValueError("short-answer problem steps require accepted answers")
        return self


class WalkthroughStep(LearnStepBase):
    type: Literal["walkthrough"]
    section_id: str = Field(alias="sectionId", min_length=1)
    component_index: int = Field(alias="componentIndex", ge=0)


LearnStep = Annotated[Union[TeachStep, MultipleChoiceStep, ShortAnswerStep, NumericAnswerStep, PredictionStep, ProblemStep, WalkthroughStep], Field(discriminator="type")]


class LearningObjective(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)
    outcome: str = Field(min_length=1, max_length=300)
    bottleneck: str = Field(min_length=1, max_length=300)
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    steps: list[LearnStep] = Field(min_length=1, max_length=8)


class LearnPlan(BaseModel):
    goal: LearnGoal
    familiarity: Familiarity
    objectives: list[LearningObjective] = Field(min_length=1, max_length=6)


class LearnSessionCreateRequest(BaseModel):
    goal: LearnGoal
    familiarity: Familiarity
    restart: bool = False


class LearnResponseRequest(BaseModel):
    response: str | None = None
    option_id: str | None = Field(default=None, alias="optionId")


class LearnHintResponse(BaseModel):
    hint: str
    hints_used: int = Field(alias="hintsUsed")


class LearnStepView(BaseModel):
    id: str
    type: str
    title: str
    prompt: str | None = None
    content: str | None = None
    options: list[LearnOption] = Field(default_factory=list)
    visual_ref: dict | None = Field(default=None, alias="visualRef")
    section_id: str | None = Field(default=None, alias="sectionId")
    component_index: int | None = Field(default=None, alias="componentIndex")
    hints_available: int = Field(default=0, alias="hintsAvailable")


class LearnSessionResponse(BaseModel):
    id: str
    document_id: int = Field(alias="documentId")
    goal: LearnGoal
    familiarity: Familiarity
    status: LearnStatus
    objective_index: int = Field(alias="objectiveIndex")
    step_index: int = Field(alias="stepIndex")
    objective_count: int = Field(alias="objectiveCount")
    objective_title: str | None = Field(default=None, alias="objectiveTitle")
    step: LearnStepView | None = None
    feedback: str | None = None
    feedback_kind: Literal["correct", "incorrect", "info"] | None = Field(default=None, alias="feedbackKind")
    hints_used: int = Field(default=0, alias="hintsUsed")
    completed_objectives: int = Field(default=0, alias="completedObjectives")
    weak_objectives: list[str] = Field(default_factory=list, alias="weakObjectives")

