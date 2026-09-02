from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class RawExtractedDocument:
    original_filename: str
    source_type: str
    markdown: str


class DocumentExtractionError(Exception):
    """A conversion failed without exposing converter internals to API callers."""


class DocumentIngestor(Protocol):
    def ingest_pdf(self, stream: BinaryIO, *, filename: str) -> RawExtractedDocument: ...
