from functools import lru_cache
from pathlib import PurePosixPath
import json
import logging
import math
import os
import re
import time

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from uuid import uuid4
from starlette.concurrency import run_in_threadpool

from app.auth_dependencies import get_current_user, require_csrf
from app.config import settings
from app.database import SessionLocal, get_db
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
from app.models.document import Document
from app.models.note import Note
from app.models.source import Source
from app.normalization import NormalizedDocument, normalize_document
from app.routing import AnthropicClassifierAdapter, ClassifierAdapter, RepresentationDecision, route_learning_block_hybrid, route_representation, should_fallback
from app.schemas.ingestion import DocumentIngestionResponse, PdfIngestionResponse, ProgressivePollResponse, ProgressiveSectionResponse, ProgressiveStartResponse
from app.segmentation import LearningBlock, segment_document
from app.services.source_index import SourceCorpusInvalid, index_document, persist_source_corpus
from app.services.usage_service import UsageClass, enforce_usage_limit
from app.semantic import AnthropicSemanticGenerator, DeterministicSemanticGenerator, HybridSemanticGenerator, PedagogicalPlanner, SemanticGenerator, SectionNote, TeachingDepth, assemble_note, plain_text_fallback, build_context_packet, group_learning_blocks, generate_sections_concurrently, generate_sections_progressively, is_low_value_section
from sqlalchemy import select


router = APIRouter(prefix="/ingestion")
logger = logging.getLogger(__name__)
_PROGRESSIVE_JOBS: dict[str, dict] = {}
PDF_MEDIA_TYPES = {"application/pdf", "application/x-pdf"}
DOCX_MEDIA_TYPES = {DOCX_MIME_TYPE}
PPTX_MEDIA_TYPES = {PPTX_MIME_TYPE}
READ_CHUNK_BYTES = 1024 * 1024


def _prune_progressive_jobs(*, now: float | None = None) -> None:
    """Evict terminal in-memory jobs after a bounded inspection window.

    Active jobs are never evicted. New work is rejected at the configured cap
    instead of discarding a running job; this is intentionally single-process
    lifecycle control, not a distributed queue.
    """
    current = time.monotonic() if now is None else now
    expired = [
        job_id
        for job_id, job in _PROGRESSIVE_JOBS.items()
        if job.get("status") in {"complete", "failed"}
        and isinstance(job.get("finished_at"), (int, float))
        and current - job["finished_at"] >= settings.progressive_job_ttl_seconds
    ]
    for job_id in expired:
        _PROGRESSIVE_JOBS.pop(job_id, None)


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


def _route_blocks(blocks: list[LearningBlock], classifier: ClassifierAdapter) -> dict[str, RepresentationDecision]:
    return {block.id: route_learning_block_hybrid(block, classifier) for block in blocks}


def estimate_ingestion_workload(blocks: list[LearningBlock]) -> dict[str, int]:
    """Estimate worst-case provider calls before routing invokes a provider."""
    source_characters = sum(max(0, int(block.character_count)) for block in blocks)
    fallback_candidates = sum(1 for block in blocks if should_fallback(route_representation(block.text)))
    eligible_sections = len([section for section in group_learning_blocks(blocks) if not is_low_value_section(section)])
    embedding_batch_size = max(1, min(int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "32")), 128))
    embedding_retries = max(0, int(os.getenv("RAG_EMBEDDING_MAX_RETRIES", "2")))
    embedding_batches = math.ceil(len(blocks) / embedding_batch_size) if blocks else 0
    provider_requests = (
        fallback_candidates * (settings.anthropic_max_retries + 1)
        + eligible_sections
        + embedding_batches * (embedding_retries + 1)
    )
    return {
        "source_characters": source_characters,
        "fallback_candidates": fallback_candidates,
        "eligible_sections": eligible_sections,
        "embedding_batches": embedding_batches,
        "provider_requests": provider_requests,
    }


def enforce_ingestion_workload(blocks: list[LearningBlock]) -> dict[str, int]:
    workload = estimate_ingestion_workload(blocks)
    if workload["source_characters"] > settings.ingestion_max_source_characters:
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "source_text_too_large",
            "This document contains too much source text to process safely. Split it into smaller documents.",
        )
    if workload["provider_requests"] > settings.ingestion_max_provider_requests:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "ingestion_workload_too_large",
            "This document would require too much processing. Split it into smaller documents.",
        )
    return workload


def _admit_and_route_ingestion(
    normalized: NormalizedDocument,
    classifier: ClassifierAdapter,
    *,
    user_id: object,
) -> tuple[list[LearningBlock], dict[str, RepresentationDecision]]:
    blocks = segment_document(normalized)
    workload = enforce_ingestion_workload(blocks)
    enforce_usage_limit(UsageClass.DOCUMENT_INGESTION, user_id)
    logger.info(
        "ingestion_workload_admitted block_count=%s source_characters=%s fallback_candidates=%s eligible_sections=%s embedding_batches=%s estimated_provider_requests=%s",
        len(blocks),
        workload["source_characters"],
        workload["fallback_candidates"],
        workload["eligible_sections"],
        workload["embedding_batches"],
        workload["provider_requests"],
    )
    return blocks, _route_blocks(blocks, classifier)

async def _generate_note(extracted, blocks, decisions, semantic_generator):
    objects, plans = {}, {}
    for index, block in enumerate(blocks):
        context = build_context_packet(block, previous=blocks[index - 1] if index else None, next_block=blocks[index + 1] if index + 1 < len(blocks) else None, document_title=extracted.filename)
        try:
            plan, obj = await run_in_threadpool(semantic_generator.generate_with_plan, block, decisions[block.id], context)
            plans[block.id] = plan
            objects[block.id] = obj
        except Exception as exc:
            logger.warning(
                "semantic_generation_fallback operation=learning_object exception_type=%s outcome=plain_text",
                type(exc).__name__,
            )
            objects[block.id] = plain_text_fallback(block)
    return assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, objects, plans)

async def _generate_section_notes(blocks, objects):
    sections = [section for section in group_learning_blocks(blocks) if not is_low_value_section(section)]
    return await generate_sections_concurrently(sections, objects, concurrency=3)

async def _generate_outputs(extracted, blocks, decisions, semantic_generator, depth: TeachingDepth = "balanced"):
    # Keep the legacy per-block note payload available for the inspector, but
    # make the user-facing coherent path section-level and model-backed.
    deterministic_objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}
    note = assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, deterministic_objects)
    objects = {section.learning_block_id: section.learning_object for section in note.sections}
    eligible_sections = [section for section in group_learning_blocks(blocks) if not is_low_value_section(section)]
    section_notes = await generate_sections_concurrently(eligible_sections, objects, concurrency=3, use_model=getattr(semantic_generator, "model_generator", None) is not None, depth=depth)
    return note, section_notes


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _safe_filename(filename: str | None, *, default: str = "upload.pdf") -> str:
    leaf = PurePosixPath((filename or default).replace("\\", "/")).name
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip()
    return (cleaned or default)[:255]


def _persist_learning_note(db, *, user_id, response: PdfIngestionResponse) -> PdfIngestionResponse:
    """Persist the completed SectionNote result through Lucent's existing
    Source -> Document -> Note ownership model.

    Re-uploading the same named source refreshes its document/note rather than
    creating an ambiguous duplicate. Different filenames and formats remain
    isolated by the per-user Source identity.
    """
    source_key = f"{response.source_type}:{response.filename}"[:255]
    source = db.execute(select(Source).where(
        Source.user_id == user_id,
        Source.type == "upload",
        Source.url == source_key,
    )).scalar_one_or_none()
    if source is None:
        source = Source(user_id=user_id, type="upload", url=source_key)
        db.add(source)
        db.flush()

    document = db.execute(select(Document).where(
        Document.source_id == source.id,
        Document.title == response.filename,
    )).scalar_one_or_none()
    if document is None:
        document = Document(source_id=source.id, title=response.filename, content=response.markdown)
        db.add(document)
        db.flush()
    else:
        document.content = response.markdown

    try:
        source_index = persist_source_corpus(db, document_id=document.id, response=response)
    except SourceCorpusInvalid as exc:
        db.rollback()
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "source_not_substantive", str(exc)) from exc

    payload = json.dumps({
        "filename": response.filename,
        "sourceType": response.source_type,
        "teachingDepth": response.teaching_depth,
        "sourceGeneration": str(source_index.generation_id),
        "sectionNotes": [note.model_dump(by_alias=True) for note in response.section_notes],
    })
    note = db.execute(select(Note).where(
        Note.document_id == document.id,
        Note.content_type == "section_note",
    )).scalar_one_or_none()
    if note is None:
        note = Note(
            title=response.filename,
            content=payload,
            content_type="section_note",
            document_id=document.id,
        )
        db.add(note)
        db.flush()
    else:
        note.title = response.filename
        note.content = payload

    db.commit()
    return response.model_copy(update={
        "source_id": source.id,
        "document_id": document.id,
        "note_id": note.id,
        "source_generation": source_index.generation_id,
        "source_index_status": source_index.status,
    })


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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db = Depends(get_db),
    ingestor: DocumentIngestor = Depends(get_document_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
    depth: TeachingDepth = Query("balanced"),
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
    blocks, decisions = await run_in_threadpool(_admit_and_route_ingestion, normalized, classifier, user_id=user.id)
    note, section_notes = await _generate_outputs(extracted, blocks, decisions, semantic_generator, depth)
    response = PdfIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, note, section_notes, teaching_depth=depth)
    persisted = _persist_learning_note(db, user_id=user.id, response=response)
    background_tasks.add_task(index_document, persisted.document_id, persisted.source_generation)
    return persisted

async def _run_progressive_job(job_id: str, extracted, blocks, decisions, semantic_generator) -> None:
    job = _PROGRESSIVE_JOBS[job_id]
    started = time.perf_counter()
    try:
        objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}

        async def on_complete(index, note, error):
            state = job["sections"][index]
            state["status"] = "complete" if error is None else "failed"
            state["section_note"] = SectionNote.model_validate(note)
            state["error"] = "Section used deterministic fallback" if error else None

        sections = [section for section in group_learning_blocks(blocks) if not is_low_value_section(section)]
        await generate_sections_progressively(sections, objects, on_complete, concurrency=3, use_model=getattr(semantic_generator, "model_generator", None) is not None, depth=job.get("depth", "balanced"))
        result = PdfIngestionResponse.model_validate({
            **job["base"].model_dump(by_alias=True),
            "section_notes": [state["section_note"] for state in job["sections"] if state["section_note"]],
        })
        with SessionLocal() as db:
            result = _persist_learning_note(db, user_id=job["user_id"], response=result)
        await run_in_threadpool(index_document, result.document_id, result.source_generation)
        job["result"] = result
        job["status"] = "complete"
        job["error"] = None
        job["finished_at"] = time.monotonic()
        logger.info(
            "ingestion_job_complete operation=progressive outcome=success exception_type=none duration_ms=%.1f section_count=%s",
            (time.perf_counter() - started) * 1000,
            len(job["sections"]),
        )
    except Exception as exc:
        # Do not attach the exception traceback/message: provider and parser
        # errors can echo source fragments. The class and operation are enough
        # to correlate this terminal job outcome without logging document text.
        logger.error(
            "ingestion_job_complete operation=progressive outcome=error exception_type=%s duration_ms=%.1f section_count=%s",
            type(exc).__name__,
            (time.perf_counter() - started) * 1000,
            len(job["sections"]),
        )
        for state in job["sections"]:
            if state["status"] in {"pending", "generating"}:
                state["status"] = "failed"
                state["error"] = "Document processing stopped before this section completed."
        job["result"] = None
        job["status"] = "failed"
        job["error"] = "Lucent could not finish processing this document. Please try again."
        job["finished_at"] = time.monotonic()

@router.post("/progressive", response_model=ProgressiveStartResponse, dependencies=[Depends(require_csrf)])
async def start_progressive_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    ingestor: DocumentIngestor = Depends(get_document_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
    depth: TeachingDepth = Query("balanced"),
) -> ProgressiveStartResponse:
    _prune_progressive_jobs()
    if len(_PROGRESSIVE_JOBS) >= settings.progressive_job_max_entries:
        await file.close()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ingestion_capacity_reached",
            "Lucent is already processing several documents. Please try again shortly.",
        )
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
    blocks, decisions = await run_in_threadpool(_admit_and_route_ingestion, normalized, classifier, user_id=user.id)
    deterministic_objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}
    base_note = assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, deterministic_objects)
    base = PdfIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, base_note, [], teaching_depth=depth)
    sections = [section for section in group_learning_blocks(blocks) if not is_low_value_section(section)]
    job_id = uuid4().hex
    _PROGRESSIVE_JOBS[job_id] = {"status": "processing", "filename": filename, "base": base, "result": None, "error": None, "finished_at": None, "user_id": user.id, "depth": depth, "sections": [{"id": section.id, "title": section.title, "learning_block_ids": section.learning_block_ids, "status": "pending", "section_note": None, "error": None} for section in sections]}
    for state in _PROGRESSIVE_JOBS[job_id]["sections"]: state["status"] = "generating"
    background_tasks.add_task(_run_progressive_job, job_id, extracted, blocks, decisions, semantic_generator)
    return ProgressiveStartResponse(job_id=job_id, filename=filename, sections=[ProgressiveSectionResponse(**state) for state in _PROGRESSIVE_JOBS[job_id]["sections"]])

@router.get("/progressive/{job_id}", response_model=ProgressivePollResponse)
async def poll_progressive_pdf(job_id: str, _user: User = Depends(get_current_user)) -> ProgressivePollResponse:
    _prune_progressive_jobs()
    job = _PROGRESSIVE_JOBS.get(job_id)
    if not job:
        raise _error(status.HTTP_404_NOT_FOUND, "job_not_found", "The ingestion job was not found")
    if job["user_id"] != _user.id:
        raise _error(status.HTTP_404_NOT_FOUND, "job_not_found", "The ingestion job was not found")
    return ProgressivePollResponse(job_id=job_id, filename=job["filename"], status=job["status"], sections=[ProgressiveSectionResponse(**state) for state in job["sections"]], result=job["result"], error=job.get("error"))


@router.post(
    "/docx",
    response_model=DocumentIngestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def ingest_docx(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db = Depends(get_db),
    ingestor: DocxDocumentIngestor = Depends(get_docx_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
    depth: TeachingDepth = Query("balanced"),
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
    blocks, decisions = await run_in_threadpool(_admit_and_route_ingestion, normalized, classifier, user_id=user.id)
    note, section_notes = await _generate_outputs(extracted, blocks, decisions, semantic_generator, depth)
    response = DocumentIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, note, section_notes, teaching_depth=depth)
    persisted = _persist_learning_note(db, user_id=user.id, response=response)
    background_tasks.add_task(index_document, persisted.document_id, persisted.source_generation)
    return persisted


@router.post(
    "/pptx",
    response_model=DocumentIngestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def ingest_pptx(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db = Depends(get_db),
    ingestor: PptxDocumentIngestor = Depends(get_pptx_ingestor),
    classifier: ClassifierAdapter = Depends(get_classifier),
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
    depth: TeachingDepth = Query("balanced"),
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
    blocks, decisions = await run_in_threadpool(_admit_and_route_ingestion, normalized, classifier, user_id=user.id)
    note, section_notes = await _generate_outputs(extracted, blocks, decisions, semantic_generator, depth)
    response = DocumentIngestionResponse.from_pipeline(extracted, normalized, blocks, decisions, note, section_notes, teaching_depth=depth)
    persisted = _persist_learning_note(db, user_id=user.id, response=response)
    background_tasks.add_task(index_document, persisted.document_id, persisted.source_generation)
    return persisted
