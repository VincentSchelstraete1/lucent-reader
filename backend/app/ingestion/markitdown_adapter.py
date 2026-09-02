from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from markitdown import MarkItDown

from app.ingestion.base import DocumentExtractionError, RawExtractedDocument


class MarkItDownDocumentIngestor:
    """Translate MarkItDown output into Lucent's raw ingestion boundary."""

    def __init__(self, converter: "MarkItDown | None" = None) -> None:
        if converter is None:
            from markitdown import MarkItDown

            converter = MarkItDown(enable_plugins=False)
        self._converter = converter

    def ingest_pdf(self, stream: BinaryIO, *, filename: str) -> RawExtractedDocument:
        try:
            from markitdown import StreamInfo

            stream.seek(0)
            result = self._converter.convert_stream(
                stream,
                stream_info=StreamInfo(
                    mimetype="application/pdf",
                    extension=".pdf",
                    filename=filename,
                ),
            )
        except Exception as exc:
            raise DocumentExtractionError("MarkItDown could not extract this PDF") from exc

        markdown = result.text_content
        if markdown is None:
            raise DocumentExtractionError("MarkItDown returned no extraction result")
        return RawExtractedDocument(
            original_filename=filename,
            source_type="pdf",
            markdown=markdown,
        )
