from typing import Literal

from pydantic import BaseModel

from app.ingestion import RawDocument, SourceLocation
from app.normalization import NormalizedDocument


class SourceLocationResponse(BaseModel):
    kind: Literal["page", "slide", "document"]
    index: int | None
    sequence_id: str | None


def _location(location: SourceLocation | None) -> SourceLocationResponse | None:
    if location is None:
        return None
    return SourceLocationResponse(kind=location.kind, index=location.index, sequence_id=location.sequence_id)


class RawContentBlockResponse(BaseModel):
    id: str
    page_number: int | None
    type: Literal["text", "image", "table", "unknown"]
    text: str | None
    bbox: tuple[float, float, float, float] | None
    reading_order: int
    image_id: str | None
    location: SourceLocationResponse | None


class RawImageResponse(BaseModel):
    id: str
    page_number: int | None
    bbox: tuple[float, float, float, float] | None
    width: int | None
    height: int | None
    mime_type: str | None
    caption: str | None
    asset_reference: str
    location: SourceLocationResponse | None


class RawPageResponse(BaseModel):
    page_number: int | None
    text: str
    blocks: list[RawContentBlockResponse]
    extraction_errors: list[str]
    location: SourceLocationResponse | None


class SourceReferenceResponse(BaseModel):
    page_start: int | None
    page_end: int | None
    raw_block_ids: list[str]
    bboxes: list[tuple[float, float, float, float]]
    locations: list[SourceLocationResponse]


class NormalizedBlockResponse(BaseModel):
    id: str
    type: Literal["heading", "paragraph", "list", "table", "caption", "image", "unknown"]
    text: str | None
    source: SourceReferenceResponse
    source_image_id: str | None


class NormalizedPageResponse(BaseModel):
    page_number: int | None
    text: str
    blocks: list[NormalizedBlockResponse]
    transformation_ids: list[str]
    suppressed_artifact_ids: list[str]
    location: SourceLocationResponse | None


class NormalizedImageResponse(BaseModel):
    id: str
    source_page: int | None
    source_bbox: tuple[float, float, float, float] | None
    width: int | None
    height: int | None
    mime_type: str | None
    caption: str | None
    asset_reference: str
    source_image_ids: list[str]
    location: SourceLocationResponse | None


class SuppressedArtifactResponse(BaseModel):
    id: str
    type: Literal["header", "footer", "page_number"]
    text: str
    page_numbers: list[int]
    raw_block_ids: list[str]


class NormalizationEventResponse(BaseModel):
    id: str
    stage: str
    page_number: int | None
    raw_block_ids: list[str]
    description: str
    before: str | None
    after: str | None


class UnresolvedArtifactResponse(BaseModel):
    id: str
    type: str
    page_number: int | None
    raw_block_ids: list[str]
    text: str
    reason: str


class NormalizationMetadataResponse(BaseModel):
    version: str
    suppressed_artifacts: list[SuppressedArtifactResponse]
    events: list[NormalizationEventResponse]
    unresolved_artifacts: list[UnresolvedArtifactResponse]
    counters: dict[str, int]


class NormalizedDocumentResponse(BaseModel):
    source_type: str
    filename: str
    page_count: int
    pages: list[NormalizedPageResponse]
    images: list[NormalizedImageResponse]
    normalization_metadata: NormalizationMetadataResponse

    @classmethod
    def from_normalized_document(cls, document: NormalizedDocument) -> "NormalizedDocumentResponse":
        metadata = document.normalization_metadata
        return cls(
            source_type=document.source_type,
            filename=document.filename,
            page_count=document.page_count,
            pages=[
                NormalizedPageResponse(
                    page_number=page.page_number,
                    text=page.text,
                    blocks=[
                        NormalizedBlockResponse(
                            id=block.id,
                            type=block.type,
                            text=block.text,
                            source=SourceReferenceResponse(
                                **{
                                    **vars(block.source),
                                    "locations": [_location(item) for item in block.source.locations],
                                }
                            ),
                            source_image_id=block.source_image_id,
                        )
                        for block in page.blocks
                    ],
                    transformation_ids=page.transformation_ids,
                    suppressed_artifact_ids=page.suppressed_artifact_ids,
                    location=_location(page.location),
                )
                for page in document.pages
            ],
            images=[
                NormalizedImageResponse(**{**vars(image), "location": _location(image.location)})
                for image in document.images
            ],
            normalization_metadata=NormalizationMetadataResponse(
                version=metadata.version,
                suppressed_artifacts=[SuppressedArtifactResponse(**vars(item)) for item in metadata.suppressed_artifacts],
                events=[NormalizationEventResponse(**vars(item)) for item in metadata.events],
                unresolved_artifacts=[UnresolvedArtifactResponse(**vars(item)) for item in metadata.unresolved_artifacts],
                counters=metadata.counters,
            ),
        )


class PdfIngestionResponse(BaseModel):
    """Shared ingestion response shape for every supported format (PDF/DOCX/PPTX) -
    the name is legacy from when only PDF was supported. New callers should use
    the format-neutral `DocumentIngestionResponse` alias below.
    """

    status: Literal["success"]
    filename: str
    source_type: Literal["pdf", "docx", "pptx"]
    page_count: int
    markdown: str
    extracted_character_count: int
    pages: list[RawPageResponse]
    images: list[RawImageResponse]
    extraction_metadata: dict[str, str | int | bool | None]
    normalized: NormalizedDocumentResponse

    @classmethod
    def from_documents(cls, document: RawDocument, normalized: NormalizedDocument) -> "PdfIngestionResponse":
        return cls(
            status="success",
            filename=document.filename,
            source_type=document.source_type,
            page_count=document.page_count,
            markdown=document.markdown,
            extracted_character_count=len(document.markdown),
            pages=[
                RawPageResponse(
                    page_number=page.page_number,
                    text=page.text,
                    blocks=[
                        RawContentBlockResponse(**{**vars(block), "location": _location(block.location)})
                        for block in page.blocks
                    ],
                    extraction_errors=page.extraction_errors,
                    location=_location(page.location),
                )
                for page in document.pages
            ],
            images=[
                RawImageResponse(**{**vars(image), "location": _location(image.location)})
                for image in document.images
            ],
            extraction_metadata=document.extraction_metadata,
            normalized=NormalizedDocumentResponse.from_normalized_document(normalized),
        )


DocumentIngestionResponse = PdfIngestionResponse
