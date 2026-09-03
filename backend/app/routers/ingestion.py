from functools import lru_cache
from pathlib import PurePosixPath
import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from uuid import uuid4
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
from app.schemas.ingestion import DocumentIngestionResponse, PdfIngestionResponse, ProgressivePollResponse, ProgressiveSectionResponse, ProgressiveStartResponse
from app.segmentation import LearningBlock, segment_document
from app.semantic import AnthropicSemanticGenerator, DeterministicSemanticGenerator, HybridSemanticGenerator, PedagogicalPlanner, SemanticGenerator, assemble_note, plain_text_fallback, build_context_packet, group_learning_blocks, generate_sections_concurrently, generate_sections_progressively


router = APIRouter(prefix="/ingestion")
_PROGRESSIVE_JOBS: dict[str, dict] = {}
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

@lru_cache(maxsize=1)
def get_semantic_generator() -> SemanticGenerator:
    return HybridSemanticGenerator(AnthropicSemanticGenerator(), planner=PedagogicalPlanner())


def _segment_and_route(
    normalized: NormalizedDocument, classifier: ClassifierAdapter
) -> tuple[list[LearningBlock], dict[str, RepresentationDecision]]:
    blocks = segment_document(normalized)
    decisions = {block.id: route_learning_block_hybrid(block, classifier) for block in blocks}
    return blocks, decisions

async def _generate_note(extracted, blocks, decisions, semantic_generator):
    objects, plans = {}, {}
    for index, block in enumerate(blocks):
        context = build_context_packet(block, previous=blocks[index - 1] if index else None, next_block=blocks[index + 1] if index + 1 < len(blocks) else None, document_title=extracted.filename)
        try:
            plan, obj = await run_in_threadpool(semantic_generator.generate_with_plan, block, decisions[block.id], context)
            plans[block.id] = plan
            objects[block.id] = obj
        except Exception:
            objects[block.id] = plain_text_fallback(block)
    return assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, objects, plans)

async def _generate_section_notes(blocks, objects):
    sections = group_learning_blocks(blocks)
    return await generate_sections_concurrently(sections, objects, concurrency=3)

async def _generate_outputs(extracted, blocks, decisions, semantic_generator):
    # Keep the legacy per-block note payload available for the inspector, but
    # make the user-facing coherent path section-level and model-backed.
    deterministic_objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}
    note = assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, deterministic_objects)
    objects = {section.learning_block_id: section.learning_object for section in note.sections}
    section_notes = await generate_sections_concurrently(group_learning_blocks(blocks), objects, concurrency=3, use_model=getattr(semantic_generator, "model_generator", None) is not None)
    return note, section_notes


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
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
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
    note, section_notes = await _generate_outputs(extracted, blocks, decisions, semantic_generator)
    return PdfIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, note, section_notes)

async def _run_progressive_job(job_id: str, extracted, blocks, decisions, semantic_generator) -> None:
    job = _PROGRESSIVE_JOBS[job_id]
    objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}
    async def on_complete(index, note, error):
        state = job["sections"][index]
        state["status"] = "complete" if error is None else "failed"
        state["section_note"] = note.model_dump(by_alias=True)
        state["error"] = "Section used deterministic fallback" if error else None
    await generate_sections_progressively(group_learning_blocks(blocks), objects, on_complete, concurrency=3, use_model=getattr(semantic_generator, "model_generator", None) is not None)
    job["status"] = "complete"

@router.post("/progressive", response_model=ProgressiveStartResponse, dependencies=[Depends(require_csrf)])
async def start_progressive_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    ingestor: DocumentIngestor = Depends(get_document_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
) -> ProgressiveStartResponse:
    if file.content_type not in PDF_MEDIA_TYPES:
        await file.close()
        raise _error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type", "Only PDF uploads are supported")
    filename = _safe_filename(file.filename)
    try:
        data = await _read_pdf(file)
    finally:
        await file.close()
    try:
        extracted = await run_in_threadpool(ingestor.ingest_pdf, data, filename=filename)
    except DocumentExtractionError:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "pdf_extraction_failed", "The PDF could not be extracted")
    normalized = await run_in_threadpool(normalize_document, extracted)
    blocks, decisions = await run_in_threadpool(_segment_and_route, normalized, classifier)
    deterministic_objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}
    base_note = assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, deterministic_objects)
    base = PdfIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, base_note, [])
    sections = group_learning_blocks(blocks)
    job_id = uuid4().hex
    _PROGRESSIVE_JOBS[job_id] = {"status": "processing", "filename": filename, "base": base, "sections": [{"id": section.id, "title": section.title, "learning_block_ids": section.learning_block_ids, "status": "pending", "section_note": None, "error": None} for section in sections]}
    for state in _PROGRESSIVE_JOBS[job_id]["sections"]: state["status"] = "generating"
    background_tasks.add_task(_run_progressive_job, job_id, extracted, blocks, decisions, semantic_generator)
    return ProgressiveStartResponse(job_id=job_id, filename=filename, sections=[ProgressiveSectionResponse(**state) for state in _PROGRESSIVE_JOBS[job_id]["sections"]])

@router.get("/progressive/{job_id}", response_model=ProgressivePollResponse)
async def poll_progressive_pdf(job_id: str, _user: User = Depends(get_current_user)) -> ProgressivePollResponse:
    job = _PROGRESSIVE_JOBS.get(job_id)
    if not job:
        raise _error(status.HTTP_404_NOT_FOUND, "job_not_found", "The ingestion job was not found")
    return ProgressivePollResponse(job_id=job_id, filename=job["filename"], status=job["status"], sections=[ProgressiveSectionResponse(**state) for state in job["sections"]], result=job["base"].model_copy(update={"section_notes": [state["section_note"] for state in job["sections"] if state["section_note"]]}) if job["status"] == "complete" else None)


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
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
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
    note, section_notes = await _generate_outputs(extracted, blocks, decisions, semantic_generator)
    return DocumentIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, note, section_notes)


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
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
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
    note, section_notes = await _generate_outputs(extracted, blocks, decisions, semantic_generator)
    return DocumentIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, note, section_notes)
