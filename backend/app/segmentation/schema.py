from dataclasses import dataclass, field
from typing import Literal

from app.normalization.schema import NormalizedBlock, SourceReference


LearningBlockType = Literal["section", "list", "table", "figure", "mixed"]

# NormalizedBlock types excluded from LearningBlock.text: a heading's text
# lives in `title`/`heading_ancestry` instead of being duplicated into the
# flowing body, and table/image blocks are structural attachments (see
# attached_table_ids/attached_image_ids) rather than prose to read inline -
# the same "reference, don't reconstruct" posture normalization already
# uses for figures.
_NON_PROSE_BLOCK_TYPES = {"heading", "table", "image"}


@dataclass(frozen=True)
class SegmentationMetadata:
    method: str
    boundary_reason: str
    version: str = "segmentation-v1"
    confidence: float | None = None


@dataclass(frozen=True)
class LearningBlock:
    """One coherent unit that should be understood or taught together.

    Distinct from NormalizedBlock ("faithfully reconstructed document
    structure"): a LearningBlock is a semantic grouping of one or more
    NormalizedBlocks, not a representation classification, LearningObject,
    render instruction, or pedagogy signal - see architecture rules.
    """

    id: str
    block_type: LearningBlockType
    text: str
    character_count: int
    normalized_block_ids: list[str]
    source: SourceReference
    segmentation: SegmentationMetadata
    title: str | None = None
    heading_ancestry: list[str] = field(default_factory=list)
    attached_table_ids: list[str] = field(default_factory=list)
    attached_image_ids: list[str] = field(default_factory=list)
    token_count: int | None = None


def merge_source_references(sources: list[SourceReference]) -> SourceReference:
    """Union several NormalizedBlock.source references into one, the same
    aggregation normalizer.py's own paragraph-merge branch already performs
    one level down (raw blocks -> one NormalizedBlock); this applies it one
    level higher (NormalizedBlocks -> one LearningBlock).
    """

    page_numbers = [
        value
        for source in sources
        for value in (source.page_start, source.page_end)
        if value is not None
    ]
    return SourceReference(
        page_start=min(page_numbers) if page_numbers else None,
        page_end=max(page_numbers) if page_numbers else None,
        raw_block_ids=[block_id for source in sources for block_id in source.raw_block_ids],
        bboxes=[bbox for source in sources for bbox in source.bboxes],
        locations=[location for source in sources for location in source.locations],
    )


def assemble_learning_block_text(constituents: list[NormalizedBlock]) -> str:
    """Join constituent prose (paragraph/list/caption/unknown-with-text) into
    one flowing body. Consecutive list blocks join with a single newline
    (they're already one visual list); everything else is paragraph-separated.
    Heading/table/image blocks are never included - see _NON_PROSE_BLOCK_TYPES.
    """

    parts: list[str] = []
    previous_type: str | None = None
    for block in constituents:
        if block.type in _NON_PROSE_BLOCK_TYPES or not block.text:
            continue
        if parts:
            parts.append("\n" if block.type == "list" and previous_type == "list" else "\n\n")
        parts.append(block.text)
        previous_type = block.type
    return "".join(parts)


def build_learning_block(
    id: str,
    *,
    constituents: list[NormalizedBlock],
    block_type: LearningBlockType,
    segmentation: SegmentationMetadata,
    title: str | None = None,
    heading_ancestry: list[str] | None = None,
    attached_table_ids: list[str] | None = None,
    attached_image_ids: list[str] | None = None,
) -> LearningBlock:
    text = assemble_learning_block_text(constituents)
    return LearningBlock(
        id=id,
        block_type=block_type,
        text=text,
        character_count=len(text),
        normalized_block_ids=[block.id for block in constituents],
        source=merge_source_references([block.source for block in constituents]),
        segmentation=segmentation,
        title=title,
        heading_ancestry=list(heading_ancestry) if heading_ancestry else [],
        attached_table_ids=list(attached_table_ids) if attached_table_ids else [],
        attached_image_ids=list(attached_image_ids) if attached_image_ids else [],
    )
