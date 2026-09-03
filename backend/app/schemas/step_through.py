from __future__ import annotations

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
    visual: StageVisual | None = None


class SequenceActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=80)


class SequenceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    receiver: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=40)
    explanation: str | None = Field(default=None, max_length=300)


class SequenceExchangeScene(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["sequence_exchange_scene"]
    actors: list[SequenceActor] = Field(min_length=2, max_length=4)
    messages: list[SequenceMessage] = Field(min_length=1, max_length=12)
    visible_message_ids: list[str] = Field(alias="visibleMessageIds", min_length=1)
    emphasized_message_id: str | None = Field(default=None, alias="emphasizedMessageId")


class VectorScene(BaseModel):
    """Semantic vector scene; layout remains a frontend concern."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["vector_scene"]
    active_entity_ids: list[str] = Field(alias="activeEntityIds", min_length=1)


class OrderedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=80)


class OrderedOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["compare", "swap", "highlight", "markComplete"]
    item_ids: list[str] = Field(alias="itemIds", min_length=1, max_length=4)
    explanation: str | None = Field(default=None, max_length=240)


class OrderedItemsScene(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["ordered_items_scene"]
    items: list[OrderedItem] = Field(min_length=2, max_length=20)
    operations: list[OrderedOperation] = Field(min_length=1, max_length=8)
    emphasized_item_ids: list[str] = Field(default_factory=list, alias="emphasizedItemIds")


StageVisual = SequenceExchangeScene | VectorScene | OrderedItemsScene


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
    scene_type: Literal["vector_scene", "sequence_exchange_scene", "ordered_items_scene"] = Field(alias="sceneType")
    title: str = Field(min_length=1, max_length=200)
    learning_goal: str = Field(alias="learningGoal", min_length=1, max_length=300)
    entities: list[StepEntity] = Field(min_length=1, max_length=20)
    stages: list[MechanismStage] = Field(min_length=2, max_length=12)
    prediction: MechanismPrediction | None = None
    conclusion: str = Field(min_length=1, max_length=700)

    @classmethod
    def generation_schema(cls) -> dict:
        return cls.model_json_schema(by_alias=True)
