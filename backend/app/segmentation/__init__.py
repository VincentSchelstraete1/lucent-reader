from app.segmentation.schema import (
    LearningBlock,
    LearningBlockType,
    SegmentationMetadata,
    assemble_learning_block_text,
    build_learning_block,
    merge_source_references,
)
from app.segmentation.segmenter import paragraph_only_baseline, segment_document
from app.segmentation.stages import SegmentationConfig

__all__ = [
    "LearningBlock",
    "LearningBlockType",
    "SegmentationConfig",
    "SegmentationMetadata",
    "assemble_learning_block_text",
    "build_learning_block",
    "merge_source_references",
    "paragraph_only_baseline",
    "segment_document",
]
