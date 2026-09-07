from dataclasses import dataclass, field
from typing import BinaryIO, Literal, Protocol


BoundingBox = tuple[float, float, float, float]
BlockType = Literal["text", "image", "table", "unknown"]
SourceType = Literal["pdf", "docx", "pptx"]
LocationKind = Literal["page", "slide", "document"]


@dataclass(frozen=True)
class SourceLocation:
    """Format-neutral provenance pointer, independent of the legacy PDF-oriented page_number field.

    kind="page" (PDF): index is the physical page number.
    kind="slide" (PPTX): index is the slide number. Never stored in page_number -
    a slide is not a page, so overloading that field would blur two distinct
    physical concepts behind one name.
    kind="document" (DOCX): index is None; sequence_id identifies position within
    the document's ordered structure (e.g. "paragraph-4", "table-1"), since DOCX
    has no trustworthy physical page boundary to point to.
    """

    kind: LocationKind
    index: int | None = None
    sequence_id: str | None = None


@dataclass(frozen=True)
class RawContentBlock:
    id: str
    page_number: int | None
    type: BlockType
    bbox: BoundingBox | None
    reading_order: int
    text: str | None = None
    image_id: str | None = None
    location: SourceLocation | None = None


@dataclass(frozen=True)
class RawImage:
    id: str
    page_number: int | None
    bbox: BoundingBox | None
    width: int | None
    height: int | None
    mime_type: str | None
    asset_reference: str
    caption: str | None = None
    location: SourceLocation | None = None


@dataclass(frozen=True)
class RawPage:
    """The ordered container for one physical page (PDF), slide (PPTX), or - for
    DOCX, which has no physical pages - the whole document's flat block sequence.

    RawPage is a legacy PDF-oriented name kept unchanged in this phase to avoid a
    broad rename; for non-paginated formats it functions as a generic ordered
    source-unit container, not a literal physical page. Use `location` (not the
    page_number-shaped identity of this class) to read a page/slide/document
    identity generically.
    """

    page_number: int | None
    text: str
    blocks: list[RawContentBlock]
    extraction_errors: list[str] = field(default_factory=list)
    location: SourceLocation | None = None


@dataclass(frozen=True)
class PageAwareExtraction:
    page_count: int
    pages: list[RawPage]
    images: list[RawImage]
    metadata: dict[str, str | int | bool | None] = field(default_factory=dict)


@dataclass(frozen=True)
class RawDocument:
    source_type: SourceType
    filename: str
    page_count: int
    markdown: str
    pages: list[RawPage]
    images: list[RawImage]
    extraction_metadata: dict[str, str | int | bool | None] = field(default_factory=dict)


class DocumentExtractionError(Exception):
    """A conversion failed without exposing extractor internals to API callers."""


class MarkdownExtractor(Protocol):
    def extract_markdown(
        self, stream: BinaryIO, *, filename: str, mimetype: str = ..., extension: str = ...
    ) -> str: ...


class PageAwarePdfExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> PageAwareExtraction: ...


class DocumentIngestor(Protocol):
    def ingest_pdf(self, pdf_bytes: bytes, *, filename: str) -> RawDocument: ...
