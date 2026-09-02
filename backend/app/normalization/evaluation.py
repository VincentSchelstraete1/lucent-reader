from dataclasses import asdict

from app.ingestion import RawDocument
from app.normalization.schema import NormalizedDocument


def build_evaluation_report(raw: RawDocument, normalized: NormalizedDocument) -> dict:
    raw_text_blocks = sum(block.type == "text" for page in raw.pages for block in page.blocks)
    normalized_text_blocks = sum(block.text is not None for page in normalized.pages for block in page.blocks)
    metadata = normalized.normalization_metadata
    return {
        "filename": raw.filename,
        "page_count": raw.page_count,
        "raw_text_blocks": raw_text_blocks,
        "normalized_text_blocks": normalized_text_blocks,
        "raw_images": len(raw.images),
        "normalized_images": len(normalized.images),
        "counters": metadata.counters,
        "suppressed_artifacts": [asdict(artifact) for artifact in metadata.suppressed_artifacts],
        "unresolved_artifacts": [asdict(artifact) for artifact in metadata.unresolved_artifacts],
    }
