from dataclasses import replace
from io import BytesIO

import pytest

from app.config import settings
from app.ingestion import DocumentExtractionError, MarkItDownDocumentIngestor, RawExtractedDocument
from app.main import app
from app.routers.ingestion import get_document_ingestor
import app.routers.ingestion as ingestion_router


class StubIngestor:
    def __init__(self, *, markdown: str = "# Extracted\n\nRaw body", error: bool = False) -> None:
        self.markdown = markdown
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def ingest_pdf(self, stream, *, filename: str) -> RawExtractedDocument:
        data = stream.read()
        self.calls.append((data, filename))
        if self.error:
            raise DocumentExtractionError("converter detail that must not leak")
        return RawExtractedDocument(filename, "pdf", self.markdown)


@pytest.fixture()
def stub_ingestor():
    stub = StubIngestor()
    app.dependency_overrides[get_document_ingestor] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_document_ingestor, None)


def test_valid_pdf_is_extracted_without_persistence(client, stub_ingestor):
    pdf = b"%PDF-1.4\nfixture bytes"
    response = client.post(
        "/ingestion/pdf",
        files={"file": ("../../lecture.pdf", pdf, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "original_filename": "lecture.pdf",
        "source_type": "pdf",
        "markdown": "# Extracted\n\nRaw body",
        "extracted_character_count": 21,
    }
    assert stub_ingestor.calls == [(pdf, "lecture.pdf")]
    assert client.get("/sources").json() == []
    assert client.get("/documents").json() == []


def test_unsupported_media_type_is_rejected(client, stub_ingestor):
    response = client.post(
        "/ingestion/pdf",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
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
    assert stub_ingestor.calls == []


@pytest.mark.parametrize(
    ("content", "error_code"),
    [(b"", "empty_pdf"), (b"plain text masquerading as pdf", "invalid_pdf")],
)
def test_empty_or_invalid_pdf_is_rejected(client, stub_ingestor, content, error_code):
    response = client.post(
        "/ingestion/pdf",
        files={"file": ("invalid.pdf", content, "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == error_code
    assert stub_ingestor.calls == []


def test_extraction_failure_returns_safe_structured_error(client):
    failing = StubIngestor(error=True)
    app.dependency_overrides[get_document_ingestor] = lambda: failing
    try:
        response = client.post(
            "/ingestion/pdf",
            files={"file": ("broken.pdf", b"%PDF-1.4\nbroken", "application/pdf")},
        )
    finally:
        app.dependency_overrides.pop(get_document_ingestor, None)

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "pdf_extraction_failed",
        "message": "MarkItDown could not extract this PDF",
    }
    assert "converter detail" not in response.text


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


def _simple_pdf_fixture(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream\nendobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


@pytest.mark.integration
def test_real_markitdown_adapter_extracts_simple_pdf():
    ingestor = MarkItDownDocumentIngestor()
    result = ingestor.ingest_pdf(
        BytesIO(_simple_pdf_fixture("Lucent ingestion fixture")),
        filename="fixture.pdf",
    )
    assert result.original_filename == "fixture.pdf"
    assert result.source_type == "pdf"
    assert "Lucent ingestion fixture" in result.markdown
