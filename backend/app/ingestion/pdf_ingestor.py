from io import BytesIO

from app.ingestion.base import DocumentIngestor, MarkdownExtractor, PageAwarePdfExtractor, RawDocument


class PdfDocumentIngestor(DocumentIngestor):
    """Assemble independent layout and Markdown extractions into one RawDocument."""

    def __init__(self, page_extractor: PageAwarePdfExtractor, markdown_extractor: MarkdownExtractor) -> None:
        self._page_extractor = page_extractor
        self._markdown_extractor = markdown_extractor

    def ingest_pdf(self, pdf_bytes: bytes, *, filename: str) -> RawDocument:
        page_aware = self._page_extractor.extract(pdf_bytes)
        markdown = self._markdown_extractor.extract_markdown(BytesIO(pdf_bytes), filename=filename)
        return RawDocument(
            source_type="pdf",
            filename=filename,
            page_count=page_aware.page_count,
            markdown=markdown,
            pages=page_aware.pages,
            images=page_aware.images,
            extraction_metadata=page_aware.metadata,
        )
