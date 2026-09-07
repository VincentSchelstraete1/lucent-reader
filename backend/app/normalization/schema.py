from dataclasses import dataclass, field
from typing import Literal

from app.ingestion.base import BoundingBox, SourceLocation


NormalizedBlockType = Literal["heading", "paragraph", "list", "table", "caption", "image", "unknown"]
SuppressionType = Literal["header", "footer", "page_number"]


@dataclass(frozen=True)
class SourceReference:
    page_start: int | None
    page_end: int | None
    raw_block_ids: list[str]
    bboxes: list[BoundingBox]
    locations: list[SourceLocation] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedBlock:
    id: str
    type: NormalizedBlockType
    text: str | None
    source: SourceReference
    source_image_id: str | None = None


@dataclass(frozen=True)
class NormalizedPage:
    page_number: int | None
    text: str
    blocks: list[NormalizedBlock]
    transformation_ids: list[str] = field(default_factory=list)
    suppressed_artifact_ids: list[str] = field(default_factory=list)
    location: SourceLocation | None = None


@dataclass(frozen=True)
class NormalizedImage:
    id: str
    source_page: int | None
    source_bbox: BoundingBox | None
    width: int | None
    height: int | None
    mime_type: str | None
    caption: str | None
    asset_reference: str
    source_image_ids: list[str]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class SuppressedArtifact:
    id: str
    type: SuppressionType
    text: str
    page_numbers: list[int]
    raw_block_ids: list[str]


@dataclass(frozen=True)
class NormalizationEvent:
    id: str
    stage: str
    page_number: int | None
    raw_block_ids: list[str]
    description: str
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class UnresolvedArtifact:
    id: str
    type: str
    page_number: int | None
    raw_block_ids: list[str]
    text: str
    reason: str


@dataclass(frozen=True)
class NormalizationMetadata:
    version: str
    suppressed_artifacts: list[SuppressedArtifact]
    events: list[NormalizationEvent]
    unresolved_artifacts: list[UnresolvedArtifact]
    counters: dict[str, int]


@dataclass(frozen=True)
class NormalizedDocument:
    source_type: str
    filename: str
    page_count: int
    pages: list[NormalizedPage]
    images: list[NormalizedImage]
    normalization_metadata: NormalizationMetadata
