from dataclasses import dataclass, field
from typing import BinaryIO, Literal, Protocol


BoundingBox = tuple[float, float, float, float]
BlockType = Literal["text", "image", "table", "unknown"]


@dataclass(frozen=True)
class RawContentBlock:
    id: str
    page_number: int
    type: BlockType
    bbox: BoundingBox | None
    reading_order: int
    text: str | None = None
    image_id: str | None = None


@dataclass(frozen=True)
class RawImage:
    id: str
    page_number: int
    bbox: BoundingBox | None
    width: int | None
    height: int | None
    mime_type: str | None
    asset_reference: str
    caption: str | None = None


@dataclass(frozen=True)
class RawPage:
    page_number: int
    text: str
    blocks: list[RawContentBlock]
    extraction_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PageAwareExtraction:
    page_count: int
    pages: list[RawPage]
    images: list[RawImage]
    metadata: dict[str, str | int | bool | None] = field(default_factory=dict)


@dataclass(frozen=True)
class RawDocument:
    source_type: Literal["pdf"]
    filename: str
    page_count: int
    markdown: str
    pages: list[RawPage]
    images: list[RawImage]
    extraction_metadata: dict[str, str | int | bool | None] = field(default_factory=dict)


class DocumentExtractionError(Exception):
    """A conversion failed without exposing extractor internals to API callers."""


class MarkdownExtractor(Protocol):
    def extract_markdown(self, stream: BinaryIO, *, filename: str) -> str: ...


class PageAwarePdfExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> PageAwareExtraction: ...


class DocumentIngestor(Protocol):
    def ingest_pdf(self, pdf_bytes: bytes, *, filename: str) -> RawDocument: ...
