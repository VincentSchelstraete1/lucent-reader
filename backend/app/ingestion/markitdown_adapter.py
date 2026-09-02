from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from markitdown import MarkItDown

from app.ingestion.base import DocumentExtractionError


class MarkItDownAdapter:
    """Expose MarkItDown as a raw Markdown extractor, not Lucent's document model."""

    def __init__(self, converter: "MarkItDown | None" = None) -> None:
        if converter is None:
            from markitdown import MarkItDown

            converter = MarkItDown(enable_plugins=False)
        self._converter = converter

    def extract_markdown(self, stream: BinaryIO, *, filename: str) -> str:
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

        if result.text_content is None:
            raise DocumentExtractionError("MarkItDown returned no extraction result")
        return result.text_content
