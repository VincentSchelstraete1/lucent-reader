import base64
import hashlib
from io import BytesIO
from typing import TYPE_CHECKING

import pymupdf

from app.ingestion.base import (
    DocumentExtractionError,
    RawContentBlock,
    RawDocument,
    RawImage,
    RawPage,
    SourceLocation,
)
from app.ingestion.markitdown_adapter import MarkItDownAdapter

if TYPE_CHECKING:
    from docx.document import Document
    from docx.table import Table


DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
HEADING_STYLE_PREFIXES = ("Heading", "Title", "Subtitle")
LIST_STYLE_MARKERS = {"List Bullet": "- ", "List Number": "1. "}


def _mime_type_from_content_type(content_type: str | None) -> str | None:
    return content_type.split(";")[0].strip() if content_type else None


def _table_text(table: "Table") -> str:
    rows = [[" ".join(cell.text.split()) for cell in row.cells] for row in table.rows]
    if not rows or not rows[0]:
        return ""
    separator = ["---"] * len(rows[0])
    lines = [rows[0], separator, *rows[1:]]
    return "\n".join("| " + " | ".join(row) + " |" for row in lines)


class DocxDocumentIngestor:
    """Extract DOCX structure into the shared RawDocument model.

    DOCX has no trustworthy physical page boundary, so the whole document
    becomes exactly one RawPage (page_number=None) - see RawPage's docstring.
    Provenance instead comes from `location` (kind="document") carrying a
    paragraph/table/image sequence_id.
    """

    def __init__(self, markdown_extractor: MarkItDownAdapter | None = None) -> None:
        self._markdown_extractor = markdown_extractor or MarkItDownAdapter()

    def ingest_docx(self, docx_bytes: bytes, *, filename: str) -> RawDocument:
        try:
            import docx
        except Exception as exc:
            raise DocumentExtractionError("The DOCX could not be opened") from exc

        try:
            document: Document = docx.Document(BytesIO(docx_bytes))
        except Exception as exc:
            raise DocumentExtractionError("The DOCX could not be opened") from exc

        blocks: list[RawContentBlock] = []
        images: list[RawImage] = []
        errors: list[str] = []
        text_lines: list[str] = []
        paragraph_count = 0
        table_count = 0
        order = 0

        try:
            for item in document.iter_inner_content():
                item_type = type(item).__name__
                if item_type == "Paragraph":
                    paragraph_count += 1
                    style_name = item.style.name if item.style else ""
                    raw_text = item.text
                    prefix = LIST_STYLE_MARKERS.get(style_name, "")
                    text = f"{prefix}{raw_text}" if prefix and raw_text.strip() else raw_text
                    if not text.strip():
                        continue
                    sequence_id = f"paragraph-{paragraph_count}"
                    blocks.append(
                        RawContentBlock(
                            id=f"docx-{sequence_id}",
                            page_number=None,
                            type="text",
                            bbox=None,
                            reading_order=order,
                            text=text,
                            location=SourceLocation(kind="document", sequence_id=sequence_id),
                        )
                    )
                    text_lines.append(text)
                    order += 1
                elif item_type == "Table":
                    table_count += 1
                    table_text = _table_text(item)
                    if not table_text:
                        continue
                    sequence_id = f"table-{table_count}"
                    blocks.append(
                        RawContentBlock(
                            id=f"docx-{sequence_id}",
                            page_number=None,
                            type="text",
                            bbox=None,
                            reading_order=order,
                            text=table_text,
                            location=SourceLocation(kind="document", sequence_id=sequence_id),
                        )
                    )
                    text_lines.append(table_text)
                    order += 1

            for image_index, shape in enumerate(document.inline_shapes, start=1):
                try:
                    blip = shape._inline.graphic.graphicData.pic.blipFill.blip
                    relationship_id = blip.embed
                    part = document.part.related_parts[relationship_id]
                    image_bytes = part.blob
                    if not image_bytes:
                        raise ValueError("empty image part")
                    pixmap = pymupdf.Pixmap(image_bytes)
                    width, height = pixmap.width, pixmap.height
                except Exception:
                    errors.append(f"Inline image {image_index} did not contain usable raster data")
                    continue
                digest = hashlib.sha256(image_bytes).hexdigest()[:16]
                sequence_id = f"image-{image_index}-{relationship_id}"
                image_id = f"docx-{sequence_id}-{digest}"
                mime_type = _mime_type_from_content_type(part.content_type)
                encoded = base64.b64encode(image_bytes).decode("ascii")
                media_type = mime_type or "application/octet-stream"
                images.append(
                    RawImage(
                        id=image_id,
                        page_number=None,
                        bbox=None,
                        width=width,
                        height=height,
                        mime_type=mime_type,
                        asset_reference=f"data:{media_type};base64,{encoded}",
                        location=SourceLocation(kind="document", sequence_id=sequence_id),
                    )
                )
                # Keep the image in the ordered source stream as a structural
                # block.  The previous implementation exposed image bytes in
                # RawDocument but omitted the corresponding block, so
                # segmentation could never attach the figure to a
                # LearningBlock.  The renderer can now associate it by ID
                # without turning the image into model-readable prose.
                blocks.append(
                    RawContentBlock(
                        id=f"docx-{sequence_id}-block",
                        page_number=None,
                        type="image",
                        bbox=None,
                        reading_order=order,
                        image_id=image_id,
                        location=SourceLocation(kind="document", sequence_id=sequence_id),
                    )
                )
                order += 1
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError("The DOCX could not be read") from exc

        page = RawPage(
            page_number=None,
            text="\n\n".join(text_lines),
            blocks=blocks,
            extraction_errors=errors,
            location=SourceLocation(kind="document"),
        )

        markdown = self._markdown_extractor.extract_markdown(
            BytesIO(docx_bytes),
            filename=filename,
            mimetype=DOCX_MIME_TYPE,
            extension=".docx",
        )

        return RawDocument(
            source_type="docx",
            filename=filename,
            page_count=1,
            markdown=markdown,
            pages=[page],
            images=images,
            extraction_metadata={
                "page_extractor": "python-docx",
                "markdown_extractor": "MarkItDown",
                "paragraph_count": paragraph_count,
                "table_count": table_count,
            },
        )
