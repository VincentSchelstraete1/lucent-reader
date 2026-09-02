from functools import lru_cache
from pathlib import PurePosixPath
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.auth_dependencies import get_current_user, require_csrf
from app.config import settings
from app.ingestion import (
    DocumentExtractionError,
    DocumentIngestor,
    DocxDocumentIngestor,
    MarkItDownAdapter,
    PdfDocumentIngestor,
    PptxDocumentIngestor,
    PyMuPDFPageExtractor,
)
from app.ingestion.docx_ingestor import DOCX_MIME_TYPE
from app.ingestion.pptx_ingestor import PPTX_MIME_TYPE
from app.models.auth import User
from app.normalization import NormalizedDocument, normalize_document
from app.routing import AnthropicClassifierAdapter, ClassifierAdapter, RepresentationDecision, route_learning_block_hybrid
from app.schemas.ingestion import DocumentIngestionResponse, PdfIngestionResponse
from app.segmentation import LearningBlock, segment_document


router = APIRouter(prefix="/ingestion")
PDF_MEDIA_TYPES = {"application/pdf", "application/x-pdf"}
DOCX_MEDIA_TYPES = {DOCX_MIME_TYPE}
PPTX_MEDIA_TYPES = {PPTX_MIME_TYPE}
READ_CHUNK_BYTES = 1024 * 1024


@lru_cache(maxsize=1)
def get_document_ingestor() -> DocumentIngestor:
    return PdfDocumentIngestor(PyMuPDFPageExtractor(), MarkItDownAdapter())


@lru_cache(maxsize=1)
def get_docx_ingestor() -> DocxDocumentIngestor:
    return DocxDocumentIngestor(MarkItDownAdapter())


@lru_cache(maxsize=1)
def get_pptx_ingestor() -> PptxDocumentIngestor:
    return PptxDocumentIngestor(MarkItDownAdapter())


@lru_cache(maxsize=1)
def get_classifier() -> ClassifierAdapter:
    return AnthropicClassifierAdapter()


def _segment_and_route(
    normalized: NormalizedDocument, classifier: ClassifierAdapter
) -> tuple[list[LearningBlock], dict[str, RepresentationDecision]]:
    blocks = segment_document(normalized)
    decisions = {block.id: route_learning_block_hybrid(block, classifier) for block in blocks}
    return blocks, decisions


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _safe_filename(filename: str | None, *, default: str = "upload.pdf") -> str:
    leaf = PurePosixPath((filename or default).replace("\\", "/")).name
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip()
    return (cleaned or default)[:255]


async def _read_pdf(upload: UploadFile) -> bytes:
    data = bytearray()
    while chunk := await upload.read(READ_CHUNK_BYTES):
        data.extend(chunk)
        if len(data) > settings.pdf_upload_max_bytes:
            raise _error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "pdf_too_large",
                f"PDF exceeds the {settings.pdf_upload_max_bytes}-byte upload limit",
            )
    if not data:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_pdf", "The uploaded PDF is empty")
    if b"%PDF-" not in data[:1024]:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_pdf", "The uploaded file is not a valid PDF")
    return bytes(data)


async def _read_office_upload(upload: UploadFile, *, format_label: str) -> bytes:
    """Chunked, size-capped read shared by the OOXML (DOCX/PPTX) routes, mirroring
    _read_pdf's shape without touching it - both formats are ZIP containers, so
    the magic-byte check ("PK\\x03\\x04") is the same for either.
    """

    data = bytearray()
    while chunk := await upload.read(READ_CHUNK_BYTES):
        data.extend(chunk)
        if len(data) > settings.pdf_upload_max_bytes:
            raise _error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"{format_label}_too_large",
                f"{format_label.upper()} exceeds the {settings.pdf_upload_max_bytes}-byte upload limit",
            )
    if not data:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, f"empty_{format_label}", f"The uploaded {format_label.upper()} is empty")
    if data[:4] != b"PK\x03\x04":
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"invalid_{format_label}",
            f"The uploaded file is not a valid {format_label.upper()}",
        )
    return bytes(data)


@router.post(
    "/pdf",
    response_model=PdfIngestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def ingest_pdf(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    ingestor: DocumentIngestor = Depends(get_document_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
) -> PdfIngestionResponse:
    if file.content_type not in PDF_MEDIA_TYPES:
        await file.close()
        raise _error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type", "Only PDF uploads are supported")

    filename = _safe_filename(file.filename)
    try:
        data = await _read_pdf(file)
    finally:
        await file.close()

    try:
        extracted = await run_in_threadpool(
            ingestor.ingest_pdf,
            data,
            filename=filename,
        )
    except DocumentExtractionError:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "pdf_extraction_failed",
            "The PDF could not be extracted",
        )

    normalized = await run_in_threadpool(normalize_document, extracted)
    blocks, decisions = await run_in_threadpool(_segment_and_route, normalized, classifier)
    return PdfIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions)


@router.post(
    "/docx",
    response_model=DocumentIngestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def ingest_docx(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    ingestor: DocxDocumentIngestor = Depends(get_docx_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
) -> DocumentIngestionResponse:
    if file.content_type not in DOCX_MEDIA_TYPES:
        await file.close()
        raise _error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type", "Only DOCX uploads are supported")

    filename = _safe_filename(file.filename, default="upload.docx")
    try:
        data = await _read_office_upload(file, format_label="docx")
    finally:
        await file.close()

    try:
        extracted = await run_in_threadpool(ingestor.ingest_docx, data, filename=filename)
    except DocumentExtractionError:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "docx_extraction_failed", "The DOCX could not be extracted")

    normalized = await run_in_threadpool(normalize_document, extracted)
    blocks, decisions = await run_in_threadpool(_segment_and_route, normalized, classifier)
    return DocumentIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions)


@router.post(
    "/pptx",
    response_model=DocumentIngestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def ingest_pptx(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    ingestor: PptxDocumentIngestor = Depends(get_pptx_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
) -> DocumentIngestionResponse:
    if file.content_type not in PPTX_MEDIA_TYPES:
        await file.close()
        raise _error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type", "Only PPTX uploads are supported")

    filename = _safe_filename(file.filename, default="upload.pptx")
    try:
        data = await _read_office_upload(file, format_label="pptx")
    finally:
        await file.close()

    try:
        extracted = await run_in_threadpool(ingestor.ingest_pptx, data, filename=filename)
    except DocumentExtractionError:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "pptx_extraction_failed", "The PPTX could not be extracted")

    normalized = await run_in_threadpool(normalize_document, extracted)
    blocks, decisions = await run_in_threadpool(_segment_and_route, normalized, classifier)
    return DocumentIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions)
