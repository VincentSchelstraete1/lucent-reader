from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _compact_generation_schema(value, *, property_map: bool = False):
    """Remove annotation-only JSON Schema keys that cost input tokens."""

    if isinstance(value, dict):
        compact = {}
        for key, item in value.items():
            if not property_map and key in {"title", "description", "default"}:
                continue
            compact[key] = _compact_generation_schema(item, property_map=key == "properties")
        return compact
    if isinstance(value, list):
        return [_compact_generation_schema(item) for item in value]
    return value


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
        return GeneratedStepThroughMechanism.generation_schema()


class GeneratedStepEntity(BaseModel):
    """Compact model-owned entity; presentation and repeated descriptions are excluded."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    kind: Literal["item", "actor", "vector", "node", "quantity"]
    label: str = Field(min_length=1, max_length=60)


class GeneratedSequenceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    sender: str = Field(min_length=1, max_length=40)
    receiver: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=160)
    result: str | None = Field(default=None, max_length=160)


class GeneratedSequenceProgram(BaseModel):
    """Shared exchange data emitted once rather than copied into every stage."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["sequence_exchange_scene"]
    actor_ids: list[str] = Field(alias="actorIds", min_length=2, max_length=4)
    messages: list[GeneratedSequenceMessage] = Field(min_length=1, max_length=8)


class GeneratedOrderedProgram(BaseModel):
    """The initial collection; later stages emit only operations and deltas."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["ordered_items_scene"]
    initial_order: list[str] = Field(alias="initialOrder", min_length=2, max_length=12)


class GeneratedVectorProgram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["vector_scene"]


GeneratedSceneProgram = Annotated[
    GeneratedSequenceProgram | GeneratedOrderedProgram | GeneratedVectorProgram,
    Field(discriminator="type"),
]


class GeneratedSequenceStage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["sequence_exchange_scene"]
    visible_message_ids: list[str] = Field(alias="visibleMessageIds", min_length=1, max_length=8)
    emphasized_message_id: str = Field(alias="emphasizedMessageId", min_length=1, max_length=40)


class GeneratedRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=12)
    status: Literal["active", "selected", "completed", "input", "output"]
    explanation: str | None = Field(default=None, max_length=140)


class GeneratedCompareOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["compare"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=2, max_length=2)
    reason: str = Field(min_length=1, max_length=160)
    result: str | None = Field(default=None, max_length=140)


class GeneratedSwapOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["swap"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=2, max_length=2)
    reason: str = Field(min_length=1, max_length=160)
    result: str = Field(min_length=1, max_length=140)


class GeneratedMoveOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["move"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=1)
    reason: str = Field(min_length=1, max_length=160)
    result: str = Field(min_length=1, max_length=140)


class GeneratedHighlightOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["highlight"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=4)
    reason: str = Field(min_length=1, max_length=160)
    result: str | None = Field(default=None, max_length=140)


class GeneratedMarkCompleteOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["mark_complete"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=4)
    reason: str = Field(min_length=1, max_length=160)
    result: str = Field(min_length=1, max_length=140)


class GeneratedOrderedObserveStage(BaseModel):
    """A comparison/highlight that does not reorder the collection."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["ordered_items_observe"]
    operation: Annotated[GeneratedCompareOperation | GeneratedHighlightOperation, Field(discriminator="type")]
    regions: list[GeneratedRegion] = Field(default_factory=list, max_length=3)


class GeneratedOrderedReorderStage(BaseModel):
    """A swap/move with one required resulting order."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["ordered_items_reorder"]
    operation: Annotated[GeneratedSwapOperation | GeneratedMoveOperation, Field(discriminator="type")]
    resulting_order: list[str] = Field(alias="resultingOrder", min_length=2, max_length=12)
    completed_entity_ids: list[str] = Field(default_factory=list, alias="completedEntityIds", max_length=12)
    regions: list[GeneratedRegion] = Field(default_factory=list, max_length=3)


class GeneratedOrderedCompleteStage(BaseModel):
    """A completion transition that cannot also reorder items."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["ordered_items_complete"]
    operation: GeneratedMarkCompleteOperation
    completed_entity_ids: list[str] = Field(alias="completedEntityIds", min_length=1, max_length=12)
    regions: list[GeneratedRegion] = Field(default_factory=list, max_length=3)


class GeneratedVectorOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["project", "subtract", "highlight", "reveal"]
    entity_ids: list[str] = Field(alias="entityIds", min_length=1, max_length=4)
    reason: str | None = Field(default=None, max_length=160)
    result: str | None = Field(default=None, max_length=140)


class GeneratedVectorRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=40)
    target: str = Field(min_length=1, max_length=40)
    relation: Literal["perpendicular_to", "projects_onto", "parallel_to"]
    explanation: str | None = Field(default=None, max_length=160)


class GeneratedVectorStage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["vector_scene"]
    active_entity_ids: list[str] = Field(alias="activeEntityIds", min_length=1, max_length=6)
    operations: list[GeneratedVectorOperation] = Field(default_factory=list, max_length=3)
    relationships: list[GeneratedVectorRelationship] = Field(default_factory=list, max_length=3)


GeneratedStageVisual = Annotated[
    GeneratedSequenceStage
    | GeneratedOrderedObserveStage
    | GeneratedOrderedReorderStage
    | GeneratedOrderedCompleteStage
    | GeneratedVectorStage,
    Field(discriminator="type"),
]


class GeneratedMechanismStage(BaseModel):
    """Only one concise teaching statement plus the semantic visual delta."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=240)
    equation: str | None = Field(default=None, max_length=160)
    notice: str | None = Field(default=None, max_length=160)
    visual: GeneratedStageVisual


class GeneratedMechanismPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=180)
    options: list[str] = Field(min_length=2, max_length=4)
    answer: int = Field(ge=0)
    reveal: str = Field(min_length=1, max_length=240)


class GeneratedStepThroughMechanism(BaseModel):
    """Bounded, non-repetitive contract sent to the model.

    It is converted deterministically into the richer canonical replay/rendering
    contract after strict validation.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["step_through_mechanism"] = "step_through_mechanism"
    scene_type: Literal["vector_scene", "sequence_exchange_scene", "ordered_items_scene"] = Field(alias="sceneType")
    title: str = Field(min_length=1, max_length=120)
    learning_goal: str = Field(alias="learningGoal", min_length=1, max_length=180)
    entities: list[GeneratedStepEntity] = Field(min_length=1, max_length=12)
    visual_program: GeneratedSceneProgram = Field(alias="visualProgram")
    stages: list[GeneratedMechanismStage] = Field(min_length=2, max_length=5)
    prediction: GeneratedMechanismPrediction | None = None
    conclusion: str = Field(min_length=1, max_length=280)

    @model_validator(mode="after")
    def validate_compact_program(self) -> "GeneratedStepThroughMechanism":
        entity_ids = [entity.id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("mechanism entities require unique IDs")
        known = set(entity_ids)
        if self.visual_program.type != self.scene_type:
            raise ValueError("visualProgram type must match sceneType")
        def stage_scene_type(stage: GeneratedMechanismStage) -> str:
            return "ordered_items_scene" if isinstance(stage.visual, (GeneratedOrderedObserveStage, GeneratedOrderedReorderStage, GeneratedOrderedCompleteStage)) else stage.visual.type

        if any(stage_scene_type(stage) != self.scene_type for stage in self.stages):
            raise ValueError("stage visual type must match sceneType")

        if isinstance(self.visual_program, GeneratedSequenceProgram):
            if {entity.id for entity in self.entities if entity.kind == "actor"} != set(self.visual_program.actor_ids) or any(entity.kind != "actor" for entity in self.entities):
                raise ValueError("sequence entities must be exactly the actors in actorIds")
            if not set(self.visual_program.actor_ids).issubset(known):
                raise ValueError("sequence actorIds must reference mechanism entities")
            message_ids = [message.id for message in self.visual_program.messages]
            if len(message_ids) != len(set(message_ids)):
                raise ValueError("sequence messages require unique IDs")
            actor_ids = set(self.visual_program.actor_ids)
            for message in self.visual_program.messages:
                if message.sender not in actor_ids or message.receiver not in actor_ids:
                    raise ValueError("sequence message endpoints must reference actorIds")
                if message.sender == message.receiver:
                    raise ValueError("sequence message sender and receiver must differ")
            known_messages = set(message_ids)
            for stage in self.stages:
                visual = stage.visual
                if not isinstance(visual, GeneratedSequenceStage):
                    raise ValueError("sequence program requires sequence stages")
                if not set(visual.visible_message_ids).issubset(known_messages):
                    raise ValueError("visibleMessageIds must reference shared messages")
                if visual.emphasized_message_id not in visual.visible_message_ids:
                    raise ValueError("emphasizedMessageId must be visible")

        elif isinstance(self.visual_program, GeneratedOrderedProgram):
            item_ids = {entity.id for entity in self.entities if entity.kind == "item"}
            if item_ids != known:
                raise ValueError("ordered programs may contain only item entities")
            if set(self.visual_program.initial_order) != item_ids or len(self.visual_program.initial_order) != len(item_ids):
                raise ValueError("initialOrder must contain every item entity exactly once")
            order = list(self.visual_program.initial_order)
            for stage in self.stages:
                visual = stage.visual
                if not isinstance(visual, (GeneratedOrderedObserveStage, GeneratedOrderedReorderStage, GeneratedOrderedCompleteStage)):
                    raise ValueError("ordered program requires ordered stages")
                if not set(visual.operation.entity_ids).issubset(order):
                    raise ValueError("ordered operation entityIds must reference collection items")
                completed_entity_ids = getattr(visual, "completed_entity_ids", [])
                if not set(completed_entity_ids).issubset(order):
                    raise ValueError("completedEntityIds must reference collection items")
                for region in visual.regions:
                    if not set(region.entity_ids).issubset(order):
                        raise ValueError("region entityIds must reference collection items")
                if isinstance(visual, GeneratedOrderedReorderStage):
                    if set(visual.resulting_order) != set(order) or len(visual.resulting_order) != len(order):
                        raise ValueError("resultingOrder must contain every collection item exactly once")
                    if visual.resulting_order == order:
                        raise ValueError(f"{visual.operation.type} must change item order")
                    order = list(visual.resulting_order)
                if isinstance(visual, GeneratedOrderedCompleteStage) and not set(visual.operation.entity_ids).issubset(visual.completed_entity_ids):
                    raise ValueError("mark_complete entities must appear in completedEntityIds")

        elif isinstance(self.visual_program, GeneratedVectorProgram):
            for stage in self.stages:
                visual = stage.visual
                if not isinstance(visual, GeneratedVectorStage):
                    raise ValueError("vector program requires vector stages")
                references = set(visual.active_entity_ids)
                references.update(entity for operation in visual.operations for entity in operation.entity_ids)
                references.update(relationship.source for relationship in visual.relationships)
                references.update(relationship.target for relationship in visual.relationships)
                if not references.issubset(known):
                    raise ValueError("vector stage must reference mechanism entities")

        if self.prediction and self.prediction.answer >= len(self.prediction.options):
            raise ValueError("prediction answer must reference an option")
        serialized = self.model_dump_json(by_alias=True).casefold()
        if any(token in serialized for token in ("<svg", "<html", "<div", "<style", "<script")):
            raise ValueError("visual programs cannot contain raw SVG, HTML, CSS, or executable code")
        return self

    @classmethod
    def generation_schema(cls) -> dict:
        return _compact_generation_schema(cls.model_json_schema(by_alias=True))

    def to_canonical(self) -> StepThroughMechanism:
        labels = {entity.id: entity.label for entity in self.entities}
        canonical_stages: list[dict] = []

        if isinstance(self.visual_program, GeneratedSequenceProgram):
            actors = [{"id": actor_id, "label": labels[actor_id]} for actor_id in self.visual_program.actor_ids]
            messages = [message.model_dump(by_alias=True, exclude_none=True) for message in self.visual_program.messages]
            message_by_id = {message.id: message for message in self.visual_program.messages}
            for stage in self.stages:
                visual = stage.visual
                assert isinstance(visual, GeneratedSequenceStage)
                emphasized = message_by_id[visual.emphasized_message_id]
                canonical_stages.append(self._canonical_stage(stage, {
                    "type": "sequence_exchange_scene",
                    "actors": actors,
                    "messages": messages,
                    "visibleMessageIds": visual.visible_message_ids,
                    "emphasizedMessageId": visual.emphasized_message_id,
                }, [emphasized.sender, emphasized.receiver]))

        elif isinstance(self.visual_program, GeneratedOrderedProgram):
            order = list(self.visual_program.initial_order)
            completed: set[str] = set()
            for stage in self.stages:
                visual = stage.visual
                assert isinstance(visual, (GeneratedOrderedObserveStage, GeneratedOrderedReorderStage, GeneratedOrderedCompleteStage))
                operation = visual.operation
                before_status = "compared" if operation.type == "compare" else "selected" if operation.type in {"swap", "move", "highlight"} else "active"
                before = {
                    "items": [{"entityId": entity_id, "status": "completed" if entity_id in completed else before_status if entity_id in operation.entity_ids else "default"} for entity_id in order],
                    "regions": [region.model_dump(by_alias=True, exclude_none=True) for region in visual.regions] if isinstance(visual, GeneratedOrderedObserveStage) else [],
                }
                scene: dict = {
                    "type": "ordered_items_scene",
                    "before": before,
                    "operation": operation.model_dump(by_alias=True, exclude_none=True),
                }
                if isinstance(visual, (GeneratedOrderedReorderStage, GeneratedOrderedCompleteStage)):
                    if isinstance(visual, GeneratedOrderedReorderStage):
                        order = list(visual.resulting_order)
                    completed.update(visual.completed_entity_ids)
                    scene["after"] = {
                        "items": [{"entityId": entity_id, "status": "completed" if entity_id in completed else "changed" if entity_id in operation.entity_ids else "default"} for entity_id in order],
                        "regions": [region.model_dump(by_alias=True, exclude_none=True) for region in visual.regions],
                    }
                canonical_stages.append(self._canonical_stage(stage, scene, operation.entity_ids))

        else:
            for stage in self.stages:
                visual = stage.visual
                assert isinstance(visual, GeneratedVectorStage)
                canonical_stages.append(self._canonical_stage(
                    stage,
                    visual.model_dump(by_alias=True, exclude_none=True),
                    visual.active_entity_ids,
                ))

        return StepThroughMechanism.model_validate({
            "type": self.type,
            "sceneType": self.scene_type,
            "title": self.title,
            "learningGoal": self.learning_goal,
            "entities": [entity.model_dump() for entity in self.entities],
            "stages": canonical_stages,
            "prediction": self.prediction.model_dump() if self.prediction else None,
            "conclusion": self.conclusion,
        })

    @staticmethod
    def _canonical_stage(stage: GeneratedMechanismStage, visual: dict, active_ids: list[str]) -> dict:
        return {
            "title": stage.title,
            "explanation": stage.explanation,
            "stateChanges": [],
            "equation": stage.equation,
            "activeEntityIds": list(dict.fromkeys(active_ids)),
            "notice": stage.notice,
            "visual": visual,
        }
