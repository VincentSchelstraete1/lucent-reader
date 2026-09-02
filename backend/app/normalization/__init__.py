from app.normalization.evaluation import build_evaluation_report
from app.normalization.normalizer import normalize_document
from app.normalization.schema import (
    NormalizationEvent,
    NormalizationMetadata,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedImage,
    NormalizedPage,
    SourceReference,
    SuppressedArtifact,
    UnresolvedArtifact,
)

__all__ = [
    "NormalizationEvent",
    "NormalizationMetadata",
    "NormalizedBlock",
    "NormalizedDocument",
    "NormalizedImage",
    "NormalizedPage",
    "SourceReference",
    "SuppressedArtifact",
    "UnresolvedArtifact",
    "build_evaluation_report",
    "normalize_document",
]
