from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

class SourceReference(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    page_start: int | None = Field(None, alias="pageStart")
    page_end: int | None = Field(None, alias="pageEnd")
    normalized_block_ids: list[str] = Field(default_factory=list, alias="normalizedBlockIds")
    locations: list[dict] = Field(default_factory=list)

class BaseObject(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    type: str
    title: str
    learning_goal: str = Field(alias="learningGoal")
    source_text: str = Field(alias="sourceText")
    source_references: list[SourceReference] = Field(default_factory=list, alias="sourceReferences")
    interactions: list[dict] = Field(default_factory=list)

class ProcessObject(BaseObject):
    type: Literal["process"]
    steps: list[dict]
    connections: list[dict]
class ComparisonObject(BaseObject):
    type: Literal["comparison"]
    items: list[dict]
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
class CausalObject(BaseObject):
    type: Literal["causal"]
    nodes: list[dict]
    edges: list[dict]
class ConceptMapObject(BaseObject):
    type: Literal["concept_map"]
    nodes: list[dict]
    relationships: list[dict]
class HierarchyObject(BaseObject):
    type: Literal["hierarchy"]
    root: dict
    edges: list[dict] = Field(default_factory=list)
class QuantitativeObject(BaseObject):
    type: Literal["quantitative"]
    formula: str | None = None
    variables: list[dict]
    given_values: list[dict] = Field(default_factory=list, alias="givenValues")
    substitutions: list[str] = Field(default_factory=list)
    derivation_steps: list[str] = Field(default_factory=list, alias="derivationSteps")
    result: str | None = None
    interpretation: str | None = None
    relationships: list[dict] = Field(default_factory=list)
class PlainTextObject(BaseObject):
    type: Literal["plain_text"]
    paragraphs: list[str]
    key_points: list[str] = Field(default_factory=list, alias="keyPoints")
    definitions: list[dict] = Field(default_factory=list)
    explanation: str | None = None
    source_grounded_context: list[str] = Field(default_factory=list, alias="sourceGroundedContext")

LearningObject = Annotated[Union[ProcessObject, ComparisonObject, CausalObject, ConceptMapObject, HierarchyObject, QuantitativeObject, PlainTextObject], Field(discriminator="type")]
