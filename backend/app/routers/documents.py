import json
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.document import DocumentCreateRequest, DocumentResponse, DocumentUpdateRequest
from app.schemas.note import NoteResponse
from app.database import get_db
from app.models.document import Document
from app.models.learning_block import DocumentSourceIndex
from app.models.note import Note
from app.models.quiz import Quiz, QuizAttempt
from app.models.source import Source
from app.schemas.ingestion import SourceIndexStatusResponse
from app.services.source_index import expire_stale_index_lease
from app.services.anthropic_service import generate_structured_note
from app.services.usage_service import UsageClass, enforce_usage_limit
from sqlalchemy import select
from app.auth_dependencies import get_current_user, require_csrf
from app.models.auth import User
router = APIRouter()

@router.post("/documents", response_model=DocumentResponse, dependencies=[Depends(require_csrf)])
def create_document(document_request: DocumentCreateRequest, db = Depends(get_db), user: User = Depends(get_current_user)):
    source = db.execute(select(Source).where(Source.id == document_request.source_id, Source.user_id == user.id)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found; document was not saved")
    if source.type == "website":
        existing = db.execute(
            select(Document).where(Document.source_id == source.id).order_by(Document.id)
        ).scalars().first()
        if existing:
            existing.title = document_request.title
            existing.content = document_request.content
            db.commit()
            db.refresh(existing)
            return existing
    document = Document(
        source_id=document_request.source_id,
        title=document_request.title,
        content=document_request.content
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document

@router.get("/documents", response_model=list[DocumentResponse])
def get_documents(db = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(Document).join(Source).where(Source.user_id == user.id)
    result = db.execute(statement)
    documents = result.scalars().all()
    return documents

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents/{document_id}/source-index", response_model=SourceIndexStatusResponse)
def get_document_source_index(document_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(
        select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    source_index = db.get(DocumentSourceIndex, document_id)
    if source_index is None:
        return SourceIndexStatusResponse(
            document_id=document_id,
            status="NOT_INDEXED",
            block_count=0,
            embedded_count=0,
            coverage_warnings=["Re-upload this document to prepare it for grounded learning."],
            retryable=False,
        )
    if expire_stale_index_lease(source_index):
        db.commit()
        db.refresh(source_index)
    return SourceIndexStatusResponse(
        document_id=document_id,
        generation_id=source_index.generation_id,
        status=source_index.status,
        block_count=source_index.block_count,
        embedded_count=source_index.embedded_count,
        coverage_warnings=list(source_index.coverage_warnings or []),
        retryable=source_index.status in {"PENDING", "FAILED"},
    )

@router.delete("/documents/{document_id}", response_model=DocumentResponse, dependencies=[Depends(require_csrf)])
def delete_document(document_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    quizzes = db.execute(select(Quiz).where(Quiz.document_id == document.id)).scalars().all()
    quiz_ids = [quiz.id for quiz in quizzes]
    if quiz_ids:
        db.query(QuizAttempt).filter(QuizAttempt.quiz_id.in_(quiz_ids)).delete(synchronize_session=False)
        db.query(Quiz).filter(Quiz.id.in_(quiz_ids)).delete(synchronize_session=False)
    db.query(Note).filter(Note.document_id == document.id).delete(synchronize_session=False)
    db.delete(document)
    db.commit()
    return document

@router.post("/documents/{document_id}/generate-note", response_model=NoteResponse, dependencies=[Depends(require_csrf)])
def generate_note(document_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_usage_limit(UsageClass.PROVIDER_GENERATION, user.id)

    try:
        generated = generate_structured_note(document.title, document.content)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    note = Note(
        title=generated.title,
        content=json.dumps(generated.model_dump()),
        content_type="generated_note",
        document_id=document.id
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@router.patch("/documents/{document_id}", response_model=DocumentResponse, dependencies=[Depends(require_csrf)])
def update_document(document_id: int, document_request: DocumentUpdateRequest, db = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.execute(select(Document).join(Source).where(Document.id == document_id, Source.user_id == user.id)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    updates = document_request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(document, key, value)
    db.commit()
    db.refresh(document)
    return document
