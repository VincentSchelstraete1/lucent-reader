from dataclasses import replace

from app.ingestion import RawDocument
from app.normalization.schema import (
    NormalizationEvent,
    NormalizationMetadata,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedImage,
    NormalizedPage,
    SourceReference,
    UnresolvedArtifact,
)
from app.normalization.stages import (
    can_merge_blocks,
    classify_block,
    detect_page_furniture,
    find_markdown_table_blocks,
    normalize_block_text,
    suspicious_concatenated_tokens,
)


NORMALIZATION_VERSION = "deterministic-v1"


def _source_reference(block) -> SourceReference:
    return SourceReference(
        page_start=block.page_number,
        page_end=block.page_number,
        raw_block_ids=[block.id],
        bboxes=[block.bbox] if block.bbox else [],
    )


def normalize_document(document: RawDocument) -> NormalizedDocument:
    suppressed_ids, suppressed_artifacts = detect_page_furniture(document)
    artifact_lookup = {
        raw_id: artifact.id for artifact in suppressed_artifacts for raw_id in artifact.raw_block_ids
    }
    events: list[NormalizationEvent] = []
    unresolved: list[UnresolvedArtifact] = []
    pages: list[NormalizedPage] = []
    counters = {
        "suppressed_headers": sum(artifact.type == "header" for artifact in suppressed_artifacts),
        "suppressed_footers": sum(artifact.type == "footer" for artifact in suppressed_artifacts),
        "suppressed_page_numbers": sum(
            len(artifact.raw_block_ids) for artifact in suppressed_artifacts if artifact.type == "page_number"
        ),
        "line_joins": 0,
        "hyphenation_repairs": 0,
        "whitespace_repairs": 0,
        "reconstructed_blocks": 0,
        "table_prose_conversions": 0,
        "markitdown_table_artifacts_flagged": 0,
        "unresolved_artifacts": 0,
    }

    for raw_page in document.pages:
        normalized_blocks: list[NormalizedBlock] = []
        page_event_ids: list[str] = []
        page_suppressed_ids: list[str] = []
        for raw_block in sorted(raw_page.blocks, key=lambda block: block.reading_order):
            if raw_block.id in suppressed_ids:
                artifact_id = artifact_lookup[raw_block.id]
                if artifact_id not in page_suppressed_ids:
                    page_suppressed_ids.append(artifact_id)
                continue
            if raw_block.type == "image":
                normalized_blocks.append(
                    NormalizedBlock(
                        id=f"normalized-{raw_block.id}",
                        type="image",
                        text=None,
                        source=_source_reference(raw_block),
                        source_image_id=raw_block.image_id,
                    )
                )
                continue
            if raw_block.type != "text" or raw_block.text is None:
                normalized_blocks.append(
                    NormalizedBlock(
                        id=f"normalized-{raw_block.id}",
                        type="unknown",
                        text=raw_block.text,
                        source=_source_reference(raw_block),
                    )
                )
                continue

            initial_type = classify_block(raw_block.text)
            transformation, uncertain_table = normalize_block_text(raw_block.text, initial_type)
            normalized_type = "paragraph" if transformation.table_prose_conversions else initial_type
            normalized = NormalizedBlock(
                id=f"normalized-{raw_block.id}",
                type=normalized_type,
                text=transformation.text,
                source=_source_reference(raw_block),
            )
            for stage, count, description in (
                ("line_reconstruction", transformation.line_joins, "Joined extraction-induced line wraps"),
                ("hyphenation_repair", transformation.hyphenation_repairs, "Repaired line-break hyphenation"),
                ("whitespace_cleanup", transformation.whitespace_repairs, "Normalized extraction whitespace"),
                ("table_artifact_repair", transformation.table_prose_conversions, "Reconstructed fragmented prose table"),
            ):
                counters_key = {
                    "line_reconstruction": "line_joins",
                    "hyphenation_repair": "hyphenation_repairs",
                    "whitespace_cleanup": "whitespace_repairs",
                    "table_artifact_repair": "table_prose_conversions",
                }[stage]
                counters[counters_key] += count
                if count:
                    event = NormalizationEvent(
                        id=f"event-{len(events) + 1}",
                        stage=stage,
                        page_number=raw_page.page_number,
                        raw_block_ids=[raw_block.id],
                        description=f"{description} ({count})",
                        before=raw_block.text,
                        after=transformation.text,
                    )
                    events.append(event)
                    page_event_ids.append(event.id)

            if uncertain_table:
                unresolved.append(
                    UnresolvedArtifact(
                        id=f"unresolved-{len(unresolved) + 1}",
                        type="ambiguous_table_layout",
                        page_number=raw_page.page_number,
                        raw_block_ids=[raw_block.id],
                        text=raw_block.text,
                        reason="Table-like syntax lacked enough evidence for safe conversion",
                    )
                )
            for token in suspicious_concatenated_tokens(transformation.text):
                unresolved.append(
                    UnresolvedArtifact(
                        id=f"unresolved-{len(unresolved) + 1}",
                        type="possible_concatenated_words",
                        page_number=raw_page.page_number,
                        raw_block_ids=[raw_block.id],
                        text=token,
                        reason="Deterministic spacing would require guessing word boundaries",
                    )
                )

            if (
                normalized_blocks
                and normalized.type == "paragraph"
                and normalized_blocks[-1].type == "paragraph"
                and can_merge_blocks(
                    normalized_blocks[-1].text or "",
                    normalized.text or "",
                    normalized_blocks[-1].source.bboxes[-1] if normalized_blocks[-1].source.bboxes else None,
                    normalized.source.bboxes[0] if normalized.source.bboxes else None,
                )
            ):
                previous = normalized_blocks[-1]
                combined_text = f"{previous.text} {normalized.text}"
                combined_source = SourceReference(
                    page_start=raw_page.page_number,
                    page_end=raw_page.page_number,
                    raw_block_ids=[*previous.source.raw_block_ids, *normalized.source.raw_block_ids],
                    bboxes=[*previous.source.bboxes, *normalized.source.bboxes],
                )
                normalized_blocks[-1] = replace(previous, text=combined_text, source=combined_source)
                counters["reconstructed_blocks"] += 1
                event = NormalizationEvent(
                    id=f"event-{len(events) + 1}",
                    stage="block_reconstruction",
                    page_number=raw_page.page_number,
                    raw_block_ids=combined_source.raw_block_ids,
                    description="Merged adjacent aligned prose fragments (1)",
                    before=f"{previous.text}\n{normalized.text}",
                    after=combined_text,
                )
                events.append(event)
                page_event_ids.append(event.id)
            else:
                normalized_blocks.append(normalized)

        page_text = "\n\n".join(block.text for block in normalized_blocks if block.text)
        pages.append(
            NormalizedPage(
                page_number=raw_page.page_number,
                text=page_text,
                blocks=normalized_blocks,
                transformation_ids=page_event_ids,
                suppressed_artifact_ids=page_suppressed_ids,
            )
        )

    for markdown_table in find_markdown_table_blocks(document.markdown):
        transformation, _uncertain = normalize_block_text(markdown_table, "table")
        if transformation.table_prose_conversions:
            counters["markitdown_table_artifacts_flagged"] += 1
            unresolved.append(
                UnresolvedArtifact(
                    id=f"unresolved-{len(unresolved) + 1}",
                    type="markitdown_probable_prose_table",
                    page_number=None,
                    raw_block_ids=[],
                    text=markdown_table,
                    reason=(
                        "The table resembles fragmented prose, but global MarkItDown output has no reliable page/block mapping; "
                        "page-aware blocks remain the normalized source"
                    ),
                )
            )

    normalized_images = [
        NormalizedImage(
            id=f"normalized-{image.id}",
            source_page=image.page_number,
            source_bbox=image.bbox,
            width=image.width,
            height=image.height,
            mime_type=image.mime_type,
            caption=image.caption,
            asset_reference=image.asset_reference,
            source_image_ids=[image.id],
        )
        for image in document.images
    ]
    counters["unresolved_artifacts"] = len(unresolved)
    return NormalizedDocument(
        source_type=document.source_type,
        filename=document.filename,
        page_count=document.page_count,
        pages=pages,
        images=normalized_images,
        normalization_metadata=NormalizationMetadata(
            version=NORMALIZATION_VERSION,
            suppressed_artifacts=suppressed_artifacts,
            events=events,
            unresolved_artifacts=unresolved,
            counters=counters,
        ),
    )
