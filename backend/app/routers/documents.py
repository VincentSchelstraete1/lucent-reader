import json
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.document import DocumentCreateRequest, DocumentResponse, DocumentUpdateRequest
from app.schemas.note import NoteResponse
from app.database import get_db
from app.models.document import Document
from app.models.note import Note
from app.services.anthropic_service import generate_structured_note
from sqlalchemy import select
router = APIRouter()

@router.post("/documents", response_model=DocumentResponse)
def create_document(document_request: DocumentCreateRequest, db = Depends(get_db)):
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
def get_documents(db = Depends(get_db)):
    statement = select(Document)
    result = db.execute(statement)
    documents = result.scalars().all()
    return documents

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.delete("/documents/{document_id}", response_model=DocumentResponse)
def delete_document(document_id: int, db = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)
    db.commit()
    return document

@router.post("/documents/{document_id}/generate-note", response_model=NoteResponse)
def generate_note(document_id: int, db = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

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

@router.patch("/documents/{document_id}", response_model=DocumentResponse)
def update_document(document_id: int, document_request: DocumentUpdateRequest, db = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    updates = document_request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(document, key, value)
    db.commit()
    db.refresh(document)
    return document
