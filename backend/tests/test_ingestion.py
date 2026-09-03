import base64
from dataclasses import replace

import pymupdf
import pytest

from app.config import settings
from app.ingestion import (
    DocumentExtractionError,
    MarkItDownAdapter,
    PageAwareExtraction,
    PdfDocumentIngestor,
    PyMuPDFPageExtractor,
    RawContentBlock,
    RawDocument,
    RawImage,
    RawPage,
)
from app.ingestion.pymupdf_extractor import associate_captions
from app.main import app
from app.routers.ingestion import get_document_ingestor
import app.routers.ingestion as ingestion_router


def _simple_pdf(*page_texts: str, include_image: bool = False) -> bytes:
    document = pymupdf.open()
    for index, text in enumerate(page_texts):
        page = document.new_page()
        page.insert_text((72, 72), text)
        if include_image and index == 0:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 12, 8), False)
            pixmap.clear_with(0x4A7C59)
            page.insert_image(pymupdf.Rect(72, 120, 192, 200), stream=pixmap.tobytes("png"))
            page.insert_text((72, 218), "Figure 1: Green fixture")
    output = document.tobytes()
    document.close()
    return output


def _raw_document(filename: str = "lecture.pdf") -> RawDocument:
    block = RawContentBlock("page-1-block-1", 1, "text", (72, 72, 200, 90), 0, "Page one")
    return RawDocument(
        source_type="pdf",
        filename=filename,
        page_count=1,
        markdown="# Extracted\n\nRaw body",
        pages=[RawPage(1, "Page one\n", [block])],
        images=[],
        extraction_metadata={"page_extractor": "stub"},
    )


class StubIngestor:
    def __init__(self, *, error: bool = False) -> None:
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def ingest_pdf(self, pdf_bytes: bytes, *, filename: str) -> RawDocument:
        self.calls.append((pdf_bytes, filename))
        if self.error:
            raise DocumentExtractionError("extractor detail that must not leak")
        return _raw_document(filename)


@pytest.fixture()
def stub_ingestor():
    stub = StubIngestor()
    app.dependency_overrides[get_document_ingestor] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_document_ingestor, None)


def test_valid_pdf_returns_structured_document_and_persists_learning_note(client, stub_ingestor):
    pdf = b"%PDF-1.4\nfixture bytes"
    response = client.post(
        "/ingestion/pdf",
        files={"file": ("../../lecture.pdf", pdf, "application/pdf")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["filename"] == "lecture.pdf"
    assert result["source_type"] == "pdf"
    assert result["page_count"] == 1
    assert result["markdown"] == "# Extracted\n\nRaw body"
    assert result["pages"][0]["page_number"] == 1
    assert result["pages"][0]["blocks"][0]["text"] == "Page one"
    assert result["images"] == []
    assert stub_ingestor.calls == [(pdf, "lecture.pdf")]
    assert isinstance(result["source_id"], int)
    assert isinstance(result["document_id"], int)
    assert isinstance(result["note_id"], int)
    assert client.get("/sources").json()[0]["url"] == "pdf:lecture.pdf"
    assert client.get("/documents").json()[0]["content"] == "# Extracted\n\nRaw body"
    stored_note = client.get(f"/notes/{result['note_id']}").json()
    assert stored_note["content_type"] == "section_note"
    assert '"sectionNotes"' in stored_note["content"]


def test_page_extractor_preserves_physical_page_count_text_and_order():
    result = PyMuPDFPageExtractor().extract(_simple_pdf("First physical page", "Second physical page"))

    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert "First physical page" in result.pages[0].text
    assert "Second physical page" in result.pages[1].text
    assert [block.reading_order for block in result.pages[0].blocks] == list(range(len(result.pages[0].blocks)))
    assert all(block.page_number == page.page_number for page in result.pages for block in page.blocks)


def test_page_extractor_preserves_image_data_page_and_safe_identifier():
    result = PyMuPDFPageExtractor().extract(_simple_pdf("Illustrated page", include_image=True))

    assert len(result.images) == 1
    image = result.images[0]
    assert image.page_number == 1
    assert image.width == 12
    assert image.height == 8
    assert image.id.startswith("page-1-image-")
    assert "/" not in image.id and ".." not in image.id
    assert image.asset_reference.startswith("data:image/png;base64,")
    assert base64.b64decode(image.asset_reference.split(",", 1)[1])
    assert any(block.image_id == image.id for block in result.pages[0].blocks)
    assert image.caption == "Figure 1: Green fixture"


def test_unusable_image_block_is_reported_without_crashing_document():
    class FakePage:
        def get_text(self, output, sort=False):
            if output == "text":
                return "Readable text"
            return {"blocks": [{"type": 1, "bbox": (0, 0, 10, 10), "width": 0, "height": 0, "image": b""}]}

    class FakeDocument:
        page_count = 1
        needs_pass = False
        is_encrypted = False

        def load_page(self, _index):
            return FakePage()

        def close(self):
            pass

    result = PyMuPDFPageExtractor(opener=lambda **_kwargs: FakeDocument()).extract(b"%PDF-fake")
    assert result.pages[0].text == "Readable text"
    assert result.pages[0].blocks[0].type == "unknown"
    assert result.pages[0].extraction_errors == ["Image block 1 did not contain usable raster data"]
    assert result.images == []


def test_obvious_nearby_caption_is_associated_but_uncertain_caption_is_not():
    image = RawImage("image-1", 1, (20, 20, 180, 120), 100, 80, "image/png", "data:image/png;base64,AA==")
    clear_caption = RawContentBlock("caption", 1, "text", (20, 125, 180, 140), 1, "Fig. 2: Cache hierarchy")
    far_caption = RawContentBlock("far", 1, "text", (20, 300, 180, 320), 2, "Figure 3: Something else")

    assert associate_captions([image], [clear_caption])[0].caption == "Fig. 2: Cache hierarchy"
    assert associate_captions([image], [far_caption])[0].caption is None
    assert associate_captions([image], [clear_caption, clear_caption])[0].caption is None


def test_pdf_ingestor_keeps_page_aware_and_markdown_representations():
    page_result = PageAwareExtraction(1, [RawPage(1, "Raw page", [])], [], {"page_extractor": "stub"})

    class Pages:
        def extract(self, pdf_bytes):
            assert pdf_bytes == b"pdf"
            return page_result

    class Markdown:
        def extract_markdown(self, stream, *, filename):
            assert stream.read() == b"pdf"
            assert filename == "input.pdf"
            return "# MarkItDown raw"

    result = PdfDocumentIngestor(Pages(), Markdown()).ingest_pdf(b"pdf", filename="input.pdf")
    assert result.pages == page_result.pages
    assert result.markdown == "# MarkItDown raw"


def test_unsupported_media_type_is_rejected(client, stub_ingestor):
    response = client.post("/ingestion/pdf", files={"file": ("notes.txt", b"not pdf", "text/plain")})
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"
    assert stub_ingestor.calls == []


def test_oversized_pdf_is_rejected(client, stub_ingestor, monkeypatch):
    monkeypatch.setattr(ingestion_router, "settings", replace(settings, pdf_upload_max_bytes=12))
    response = client.post(
        "/ingestion/pdf",
        files={"file": ("large.pdf", b"%PDF-1.4\nmore than twelve bytes", "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "pdf_too_large"


@pytest.mark.parametrize("content,code", [(b"", "empty_pdf"), (b"not really a PDF", "invalid_pdf")])
def test_empty_or_invalid_pdf_is_rejected(client, stub_ingestor, content, code):
    response = client.post("/ingestion/pdf", files={"file": ("invalid.pdf", content, "application/pdf")})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_extraction_failure_returns_safe_structured_error(client):
    app.dependency_overrides[get_document_ingestor] = lambda: StubIngestor(error=True)
    try:
        response = client.post(
            "/ingestion/pdf",
            files={"file": ("broken.pdf", b"%PDF-1.4\nbroken", "application/pdf")},
        )
    finally:
        app.dependency_overrides.pop(get_document_ingestor, None)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "pdf_extraction_failed"
    assert "extractor detail" not in response.text


def test_pdf_ingestion_requires_authentication(unauthenticated_client, stub_ingestor):
    response = unauthenticated_client.post(
        "/ingestion/pdf",
        files={"file": ("lecture.pdf", b"%PDF-1.4\nfixture", "application/pdf")},
    )
    assert response.status_code == 401
    assert stub_ingestor.calls == []


def test_pdf_ingestion_requires_csrf_for_cookie_session(client, stub_ingestor):
    client.headers.pop("X-CSRF-Token")
    response = client.post(
        "/ingestion/pdf",
        files={"file": ("lecture.pdf", b"%PDF-1.4\nfixture", "application/pdf")},
    )
    assert response.status_code == 403
    assert stub_ingestor.calls == []


@pytest.mark.integration
def test_real_extractors_return_pages_images_and_markdown():
    pdf = _simple_pdf("Lucent ingestion fixture", include_image=True)
    result = PdfDocumentIngestor(PyMuPDFPageExtractor(), MarkItDownAdapter()).ingest_pdf(pdf, filename="fixture.pdf")
    assert result.page_count == 1
    assert "Lucent ingestion fixture" in result.pages[0].text
    assert "Lucent ingestion fixture" in result.markdown
    assert len(result.images) == 1
