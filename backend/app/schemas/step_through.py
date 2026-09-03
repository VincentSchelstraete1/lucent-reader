from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StepEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["item", "actor", "vector", "node", "quantity"] = "node"
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=240)


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
    notice: str | None = Field(default=None, max_length=240)
    insight: str | None = Field(default=None, max_length=300)
    visual: StageVisual


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
    reason: str | None = Field(default=None, max_length=300)
    result: str | None = Field(default=None, max_length=240)


class SequenceExchangeScene(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["sequence_exchange_scene"]
    actors: list[SequenceActor] = Field(min_length=2, max_length=4)
    messages: list[SequenceMessage] = Field(min_length=1, max_length=12)
    visible_message_ids: list[str] = Field(alias="visibleMessageIds", min_length=1)
    emphasized_message_id: str | None = Field(default=None, alias="emphasizedMessageId")

    @model_validator(mode="after")
    def validate_references(self) -> "SequenceExchangeScene":
        actor_ids = [actor.id for actor in self.actors]
        message_ids = [message.id for message in self.messages]
        if len(actor_ids) != len(set(actor_ids)) or len(message_ids) != len(set(message_ids)):
            raise ValueError("sequence actors and messages require unique IDs")
        actors = set(actor_ids)
        for message in self.messages:
            if message.sender not in actors or message.receiver not in actors:
                raise ValueError("sequence message sender and receiver must reference actors")
            if message.sender == message.receiver:
                raise ValueError("sequence message sender and receiver must differ")
        if not set(self.visible_message_ids).issubset(message_ids):
            raise ValueError("visibleMessageIds must reference sequence messages")
        if self.emphasized_message_id and self.emphasized_message_id not in message_ids:
            raise ValueError("emphasizedMessageId must reference a sequence message")
        return self


class VectorOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["project", "subtract", "highlight", "reveal"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=4)
    reason: str | None = Field(default=None, max_length=300)
    result: str | None = Field(default=None, max_length=240)


class VectorRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relation: Literal["perpendicular_to", "projects_onto", "parallel_to"]
    explanation: str | None = Field(default=None, max_length=300)


class VectorScene(BaseModel):
    """Semantic vector scene; layout remains a frontend concern."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["vector_scene"]
    active_entity_ids: list[str] = Field(alias="activeEntityIds", min_length=1)
    operations: list[VectorOperation] = Field(default_factory=list, max_length=6)
    relationships: list[VectorRelationship] = Field(default_factory=list, max_length=6)


class OrderedStateItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    entity_id: str = Field(alias="entityId", min_length=1)
    status: Literal["default", "active", "selected", "compared", "changed", "completed", "inactive"] = "default"


class SemanticRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=80)
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=20)
    status: Literal["active", "selected", "completed", "input", "output"]
    explanation: str | None = Field(default=None, max_length=240)


class OrderedCollectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderedStateItem] = Field(min_length=2, max_length=20)
    regions: list[SemanticRegion] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_state(self) -> "OrderedCollectionState":
        item_ids = [item.entity_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("ordered state cannot contain duplicate entity references")
        item_id_set = set(item_ids)
        region_ids: set[str] = set()
        for region in self.regions:
            if region.id in region_ids:
                raise ValueError("ordered regions require unique IDs")
            region_ids.add(region.id)
            if not set(region.entity_ids).issubset(item_id_set):
                raise ValueError("ordered region entityIds must reference state items")
        return self


class OrderedOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["compare", "swap", "move", "highlight", "mark_complete"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=4)
    reason: str | None = Field(default=None, max_length=300)
    result: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_arity(self) -> "OrderedOperation":
        if self.type in {"compare", "swap"} and len(self.entity_ids) != 2:
            raise ValueError(f"{self.type} requires exactly two entityIds")
        if self.type == "move" and len(self.entity_ids) != 1:
            raise ValueError("move requires exactly one entityId")
        if self.type in {"compare", "swap", "move", "mark_complete"} and not self.reason:
            raise ValueError(f"{self.type} requires a learner-facing reason")
        if self.type in {"swap", "move", "mark_complete"} and not self.result:
            raise ValueError(f"{self.type} requires a learner-facing result")
        return self


class OrderedItemsScene(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["ordered_items_scene"]
    before: OrderedCollectionState
    operation: OrderedOperation
    after: OrderedCollectionState | None = None
    notice: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_transition(self) -> "OrderedItemsScene":
        before_ids = [item.entity_id for item in self.before.items]
        before_set = set(before_ids)
        if not set(self.operation.entity_ids).issubset(before_set):
            raise ValueError("ordered operation entityIds must reference before-state items")
        if self.after:
            after_ids = [item.entity_id for item in self.after.items]
            if set(after_ids) != before_set:
                raise ValueError("ordered before and after states must contain the same entities")
        if self.operation.type in {"swap", "move", "mark_complete"} and self.after is None:
            raise ValueError(f"{self.operation.type} requires an after state")
        if self.operation.type in {"swap", "move"} and self.after:
            after_ids = [item.entity_id for item in self.after.items]
            if after_ids == before_ids:
                raise ValueError(f"{self.operation.type} must change item order")
        if self.operation.type == "mark_complete" and self.after:
            after_ids = [item.entity_id for item in self.after.items]
            if after_ids != before_ids:
                raise ValueError("mark_complete cannot also reorder items")
            completed = {item.entity_id for item in self.after.items if item.status == "completed"}
            if not set(self.operation.entity_ids).issubset(completed):
                raise ValueError("mark_complete entities must be completed in the after state")
        return self


StageVisual = Annotated[SequenceExchangeScene | VectorScene | OrderedItemsScene, Field(discriminator="type")]


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

    @model_validator(mode="after")
    def validate_semantic_program(self) -> "StepThroughMechanism":
        entity_ids = [entity.id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("mechanism entities require unique IDs")
        known = set(entity_ids)
        for stage in self.stages:
            if not set(stage.active_entity_ids).issubset(known):
                raise ValueError("activeEntityIds must reference mechanism entities")
            if any(change.entity_id not in known for change in stage.state_changes):
                raise ValueError("stateChanges must reference mechanism entities")
            if stage.visual.type != self.scene_type:
                raise ValueError("stage visual type must match sceneType")
            if isinstance(stage.visual, OrderedItemsScene):
                referenced = {item.entity_id for item in stage.visual.before.items}
                if stage.visual.after:
                    referenced.update(item.entity_id for item in stage.visual.after.items)
                if not referenced.issubset(known):
                    raise ValueError("ordered states must reference mechanism entities")
            elif isinstance(stage.visual, VectorScene):
                references = set(stage.visual.active_entity_ids)
                references.update(entity for operation in stage.visual.operations for entity in operation.entity_ids)
                references.update(relationship.source for relationship in stage.visual.relationships)
                references.update(relationship.target for relationship in stage.visual.relationships)
                if not references.issubset(known):
                    raise ValueError("vector scene must reference mechanism entities")
            elif isinstance(stage.visual, SequenceExchangeScene):
                if not {actor.id for actor in stage.visual.actors}.issubset(known):
                    raise ValueError("sequence actors must reference mechanism entities")
        if self.prediction and self.prediction.answer >= len(self.prediction.options):
            raise ValueError("prediction answer must reference an option")
        serialized = self.model_dump_json(by_alias=True).casefold()
        if any(token in serialized for token in ("<svg", "<html", "<div", "<style", "<script")):
            raise ValueError("visual programs cannot contain raw SVG, HTML, CSS, or executable code")
        return self

    @classmethod
    def generation_schema(cls) -> dict:
        return cls.model_json_schema(by_alias=True)
