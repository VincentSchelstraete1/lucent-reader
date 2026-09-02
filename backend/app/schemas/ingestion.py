from typing import Literal

from pydantic import BaseModel

from app.ingestion import RawDocument


class RawContentBlockResponse(BaseModel):
    id: str
    page_number: int
    type: Literal["text", "image", "table", "unknown"]
    text: str | None
    bbox: tuple[float, float, float, float] | None
    reading_order: int
    image_id: str | None


class RawImageResponse(BaseModel):
    id: str
    page_number: int
    bbox: tuple[float, float, float, float] | None
    width: int | None
    height: int | None
    mime_type: str | None
    caption: str | None
    asset_reference: str


class RawPageResponse(BaseModel):
    page_number: int
    text: str
    blocks: list[RawContentBlockResponse]
    extraction_errors: list[str]


class PdfIngestionResponse(BaseModel):
    status: Literal["success"]
    filename: str
    source_type: Literal["pdf"]
    page_count: int
    markdown: str
    extracted_character_count: int
    pages: list[RawPageResponse]
    images: list[RawImageResponse]
    extraction_metadata: dict[str, str | int | bool | None]

    @classmethod
    def from_raw_document(cls, document: RawDocument) -> "PdfIngestionResponse":
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
                    blocks=[RawContentBlockResponse(**vars(block)) for block in page.blocks],
                    extraction_errors=page.extraction_errors,
                )
                for page in document.pages
            ],
            images=[RawImageResponse(**vars(image)) for image in document.images],
            extraction_metadata=document.extraction_metadata,
        )
