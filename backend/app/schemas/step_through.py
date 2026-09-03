from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StepEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    color: str | None = None


class StateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(alias="entityId", min_length=1)
    change: str = Field(min_length=1, max_length=240)
    why: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MechanismStage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str = Field(min_length=1, max_length=160)
    explanation: str = Field(min_length=1, max_length=700)
    state_changes: list[StateChange] = Field(default_factory=list, alias="stateChanges")
    equation: str | None = Field(default=None, max_length=240)
    active_entity_ids: list[str] = Field(default_factory=list, alias="activeEntityIds")


class MechanismPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=5)
    answer: int = Field(ge=0)
    reveal: str = Field(min_length=1, max_length=500)


class StepThroughMechanism(BaseModel):
    """Semantic contract for the generic step-through renderer.

    Coordinates, SVG, colors-as-layout, and other presentation details are
    deliberately not part of this contract. The browser owns layout.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["step_through_mechanism"] = "step_through_mechanism"
    title: str = Field(min_length=1, max_length=200)
    learning_goal: str = Field(alias="learningGoal", min_length=1, max_length=300)
    entities: list[StepEntity] = Field(min_length=1, max_length=20)
    stages: list[MechanismStage] = Field(min_length=2, max_length=12)
    prediction: MechanismPrediction | None = None
    conclusion: str = Field(min_length=1, max_length=700)

    @classmethod
    def generation_schema(cls) -> dict:
        return cls.model_json_schema(by_alias=True)
