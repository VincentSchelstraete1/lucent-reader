import base64
import hashlib
import re
from collections.abc import Callable
from typing import Any

import pymupdf

from app.ingestion.base import (
    BoundingBox,
    DocumentExtractionError,
    PageAwareExtraction,
    RawContentBlock,
    RawImage,
    RawPage,
)


CAPTION_PATTERN = re.compile(r"^(?:figure|fig\.|table)\s+\d+[a-z]?(?:\s*[:.\-]|\s+)", re.IGNORECASE)
MAX_CAPTION_GAP_POINTS = 72.0
MIN_HORIZONTAL_OVERLAP_RATIO = 0.25


def _bbox(value: Any) -> BoundingBox | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        coordinates = tuple(float(coordinate) for coordinate in value)
    except (TypeError, ValueError):
        return None
    return coordinates[0], coordinates[1], coordinates[2], coordinates[3]


def _text_from_block(block: dict[str, Any]) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = [str(span.get("text", "")) for span in line.get("spans", [])]
        lines.append("".join(spans))
    return "\n".join(lines)


def _mime_type(extension: str | None) -> str | None:
    normalized = (extension or "").lower().lstrip(".")
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "jpx": "image/jp2",
        "jp2": "image/jp2",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }.get(normalized)


def _horizontal_overlap_ratio(first: BoundingBox, second: BoundingBox) -> float:
    overlap = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    denominator = min(max(first[2] - first[0], 0.0), max(second[2] - second[0], 0.0))
    return overlap / denominator if denominator else 0.0


def associate_captions(images: list[RawImage], blocks: list[RawContentBlock]) -> list[RawImage]:
    candidates = [
        block
        for block in blocks
        if block.type == "text" and block.text and block.bbox and CAPTION_PATTERN.match(block.text.strip())
    ]
    associated: list[RawImage] = []
    for image in images:
        matches: list[tuple[float, RawContentBlock]] = []
        if image.bbox:
            for candidate in candidates:
                if candidate.page_number != image.page_number or not candidate.bbox:
                    continue
                vertical_gap = min(
                    abs(candidate.bbox[1] - image.bbox[3]),
                    abs(image.bbox[1] - candidate.bbox[3]),
                )
                if (
                    vertical_gap <= MAX_CAPTION_GAP_POINTS
                    and _horizontal_overlap_ratio(image.bbox, candidate.bbox) >= MIN_HORIZONTAL_OVERLAP_RATIO
                ):
                    matches.append((vertical_gap, candidate))
        matches.sort(key=lambda item: item[0])
        caption = matches[0][1].text.strip() if len(matches) == 1 else None
        associated.append(
            RawImage(
                id=image.id,
                page_number=image.page_number,
                bbox=image.bbox,
                width=image.width,
                height=image.height,
                mime_type=image.mime_type,
                asset_reference=image.asset_reference,
                caption=caption,
            )
        )
    return associated


class PyMuPDFPageExtractor:
    """Preserve physical PDF pages, layout blocks, and rendered image bytes."""

    def __init__(self, opener: Callable[..., Any] = pymupdf.open) -> None:
        self._opener = opener

    def extract(self, pdf_bytes: bytes) -> PageAwareExtraction:
        try:
            document = self._opener(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise DocumentExtractionError("The PDF could not be opened") from exc

        try:
            if document.needs_pass:
                raise DocumentExtractionError("Password-protected PDFs are not supported")
            pages: list[RawPage] = []
            images: list[RawImage] = []
            for page_index in range(document.page_count):
                page_number = page_index + 1
                page_blocks: list[RawContentBlock] = []
                page_images: list[RawImage] = []
                errors: list[str] = []
                page_text = ""
                try:
                    page = document.load_page(page_index)
                    page_text = page.get_text("text", sort=False)
                    raw_blocks = page.get_text("dict", sort=False).get("blocks", [])
                    for order, block in enumerate(raw_blocks):
                        block_id = f"page-{page_number}-block-{order + 1}"
                        block_bbox = _bbox(block.get("bbox"))
                        if block.get("type") == 0:
                            page_blocks.append(
                                RawContentBlock(
                                    id=block_id,
                                    page_number=page_number,
                                    type="text",
                                    text=_text_from_block(block),
                                    bbox=block_bbox,
                                    reading_order=order,
                                )
                            )
                        elif block.get("type") == 1:
                            image_bytes = block.get("image")
                            width = block.get("width")
                            height = block.get("height")
                            if not isinstance(image_bytes, bytes) or not image_bytes or not width or not height:
                                errors.append(f"Image block {order + 1} did not contain usable raster data")
                                page_blocks.append(RawContentBlock(block_id, page_number, "unknown", block_bbox, order))
                                continue
                            mime_type = _mime_type(block.get("ext"))
                            digest = hashlib.sha256(image_bytes).hexdigest()[:16]
                            image_id = f"page-{page_number}-image-{order + 1}-{digest}"
                            encoded = base64.b64encode(image_bytes).decode("ascii")
                            media_type = mime_type or "application/octet-stream"
                            page_images.append(
                                RawImage(
                                    id=image_id,
                                    page_number=page_number,
                                    bbox=block_bbox,
                                    width=int(width),
                                    height=int(height),
                                    mime_type=mime_type,
                                    asset_reference=f"data:{media_type};base64,{encoded}",
                                )
                            )
                            page_blocks.append(
                                RawContentBlock(
                                    id=block_id,
                                    page_number=page_number,
                                    type="image",
                                    bbox=block_bbox,
                                    reading_order=order,
                                    image_id=image_id,
                                )
                            )
                        else:
                            page_blocks.append(RawContentBlock(block_id, page_number, "unknown", block_bbox, order))
                    page_images = associate_captions(page_images, page_blocks)
                except Exception:
                    errors.append(f"Page {page_number} could not be extracted")
                pages.append(RawPage(page_number, page_text, page_blocks, errors))
                images.extend(page_images)

            metadata = {
                "page_extractor": "PyMuPDF",
                "page_extractor_version": pymupdf.version[0],
                "markdown_extractor": "MarkItDown",
                "encrypted": bool(document.is_encrypted),
            }
            return PageAwareExtraction(document.page_count, pages, images, metadata)
        finally:
            document.close()
