from functools import lru_cache
from io import BytesIO
from pathlib import PurePosixPath
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.auth_dependencies import get_current_user, require_csrf
from app.config import settings
from app.ingestion import DocumentExtractionError, DocumentIngestor, MarkItDownDocumentIngestor
from app.models.auth import User
from app.schemas.ingestion import PdfIngestionResponse


router = APIRouter(prefix="/ingestion")
PDF_MEDIA_TYPES = {"application/pdf", "application/x-pdf"}
READ_CHUNK_BYTES = 1024 * 1024


@lru_cache(maxsize=1)
def get_document_ingestor() -> DocumentIngestor:
    return MarkItDownDocumentIngestor()


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _safe_filename(filename: str | None) -> str:
    leaf = PurePosixPath((filename or "upload.pdf").replace("\\", "/")).name
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip()
    return (cleaned or "upload.pdf")[:255]


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


@router.post(
    "/pdf",
    response_model=PdfIngestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def ingest_pdf(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    ingestor: DocumentIngestor = Depends(get_document_ingestor),
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
            BytesIO(data),
            filename=filename,
        )
    except DocumentExtractionError:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "pdf_extraction_failed",
            "MarkItDown could not extract this PDF",
        )

    return PdfIngestionResponse(
        status="success",
        original_filename=extracted.original_filename,
        source_type="pdf",
        markdown=extracted.markdown,
        extracted_character_count=len(extracted.markdown),
    )
