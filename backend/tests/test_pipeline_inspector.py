import pytest

from app.ingestion import RawContentBlock, RawDocument, RawPage
from app.ingestion.base import SourceLocation
from app.main import app
from app.routers.ingestion import get_classifier, get_document_ingestor


def _raw_document(filename: str = "lecture.pdf") -> RawDocument:
    page_location = SourceLocation(kind="page", index=1)
    heading = RawContentBlock("page-1-block-1", 1, "text", (72, 40, 300, 60), 0, "Cache Associativity", location=page_location)
    body = RawContentBlock(
        "page-1-block-2", 1, "text", (72, 70, 500, 120), 1,
        "Direct-mapped caches place a block in exactly one location.", location=page_location,
    )
    return RawDocument(
        source_type="pdf", filename=filename, page_count=1,
        markdown="# Cache Associativity\n\nDirect-mapped caches place a block in exactly one location.",
        pages=[RawPage(1, "Cache Associativity\nDirect-mapped caches place a block in exactly one location.", [heading, body], location=page_location)],
        images=[],
    )


class StubIngestor:
    def ingest_pdf(self, pdf_bytes: bytes, *, filename: str) -> RawDocument:
        return _raw_document(filename)


class StubClassifier:
    def __init__(self, result):
        self.result = result

    def classify(self, text: str):
        return self.result


@pytest.fixture()
def stub_pipeline_ingestor():
    app.dependency_overrides[get_document_ingestor] = lambda: StubIngestor()
    yield
    app.dependency_overrides.pop(get_document_ingestor, None)


def test_ingestion_endpoint_returns_full_pipeline_through_deterministic_routing(client, stub_pipeline_ingestor):
    # conftest.py's default _NullClassifier means every decision here should
    # be deterministic - "Direct-mapped caches place a block in exactly one
    # location." doesn't clear the structured threshold, so it should land
    # on plain_text without a fallback call.
    response = client.post("/ingestion/pdf", files={"file": ("lecture.pdf", b"%PDF-1.4\nfixture", "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert "learning_blocks" in body
    blocks = body["learning_blocks"]
    assert len(blocks) == 1
    block = blocks[0]
    assert block["title"] == "Cache Associativity"
    assert block["block_type"] == "section"
    assert "Direct-mapped caches" in block["text"]
    assert block["character_count"] == len(block["text"])
    assert block["normalized_block_ids"]
    assert block["source"]["locations"]
    assert block["heading_ancestry"] == []
    assert block["segmentation_method"] == "structural"
    assert "Cache Associativity" in block["segmentation_boundary_reason"]
    representation = block["representation"]
    assert representation["learning_block_id"] == block["id"]
    assert representation["method"] == "deterministic"
    assert representation["fallback_used"] is False
    assert len(representation["scores"]) == 7


def test_ingestion_endpoint_uses_classifier_fallback_when_uncertain(client, stub_pipeline_ingestor):
    app.dependency_overrides[get_classifier] = lambda: StubClassifier("causal")
    try:
        response = client.post("/ingestion/pdf", files={"file": ("lecture.pdf", b"%PDF-1.4\nfixture", "application/pdf")})
    finally:
        app.dependency_overrides.pop(get_classifier, None)

    assert response.status_code == 200
    block = response.json()["learning_blocks"][0]
    representation = block["representation"]
    assert representation["method"] == "fallback_classifier"
    assert representation["fallback_used"] is True
    assert representation["type"] == "causal"
    assert representation["confidence"] is None


def test_ingestion_endpoint_without_pipeline_still_omits_learning_blocks_by_default():
    # PdfIngestionResponse.from_documents() (used by direct-construction
    # callers, not the live endpoints) leaves learning_blocks empty rather
    # than requiring every caller to run the full pipeline.
    from app.normalization import normalize_document
    from app.schemas.ingestion import PdfIngestionResponse

    raw = _raw_document()
    normalized = normalize_document(raw)
    response = PdfIngestionResponse.from_documents(raw, normalized)
    assert response.learning_blocks == []
