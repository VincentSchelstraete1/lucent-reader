from app.normalization.schema import NormalizedDocument
from app.segmentation.schema import LearningBlock, SegmentationMetadata, build_learning_block
from app.segmentation.stages import (
    SegmentationConfig,
    attached_ids,
    boundary_reason,
    group_structurally,
    infer_block_type,
    split_for_size,
)


def segment_document(
    document: NormalizedDocument,
    config: SegmentationConfig | None = None,
    *,
    apply_size_constraints: bool = True,
) -> list[LearningBlock]:
    """NormalizedDocument -> structural segmentation -> [size/coherence
    adjustment] -> LearningBlock[]. `apply_size_constraints=False` yields the
    pure structural-only candidate, used by the evaluation harness to compare
    strategies without duplicating the grouping logic.
    """

    config = config or SegmentationConfig()
    groups = group_structurally(document)
    if apply_size_constraints:
        groups = split_for_size(groups, config)

    blocks: list[LearningBlock] = []
    for index, group in enumerate(groups, start=1):
        method, reason = boundary_reason(group, config, is_leading=(index == 1 and group.title is None))
        table_ids, image_ids = attached_ids(group.blocks)
        blocks.append(
            build_learning_block(
                f"learning-block-{index}",
                constituents=group.blocks,
                block_type=infer_block_type(group.blocks, group.title, group.ancestry),
                segmentation=SegmentationMetadata(method=method, boundary_reason=reason),
                title=group.title,
                heading_ancestry=group.ancestry,
                attached_table_ids=table_ids,
                attached_image_ids=image_ids,
            )
        )
    return blocks


def paragraph_only_baseline(document: NormalizedDocument) -> list[LearningBlock]:
    """One LearningBlock per NormalizedBlock - the naive baseline the
    evaluation harness compares structural segmentation against."""

    blocks: list[LearningBlock] = []
    index = 0
    for page in document.pages:
        for block in page.blocks:
            index += 1
            table_ids = [block.id] if block.type == "table" else []
            image_ids = [block.source_image_id] if block.type == "image" and block.source_image_id else []
            blocks.append(
                build_learning_block(
                    f"learning-block-{index}",
                    constituents=[block],
                    block_type="section" if block.type == "heading" else infer_block_type([block], None, []),
                    segmentation=SegmentationMetadata(method="paragraph_only", boundary_reason="Baseline: one NormalizedBlock per LearningBlock."),
                    title=block.text if block.type == "heading" else None,
                    attached_table_ids=table_ids,
                    attached_image_ids=image_ids,
                )
            )
    return blocks
