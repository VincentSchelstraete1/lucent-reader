from fastapi import APIRouter, Depends, HTTPException
from app.schemas.note import NoteCreateRequest, NoteResponse, NoteUpdateRequest
from app.database import get_db
from app.models.note import Note
from app.models.document import Document
from sqlalchemy import select
from app.models.source import Source
from app.auth_dependencies import get_current_user, require_csrf
from app.models.auth import User
router = APIRouter()

@router.post("/notes", response_model=NoteResponse, dependencies=[Depends(require_csrf)])
def create_note(note_request: NoteCreateRequest, db = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.execute(select(Document).join(Source).where(Document.id == note_request.document_id, Source.user_id == user.id)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found; note was not saved")

    note = Note(
        title=note_request.title,
        content=note_request.content,
        source_passage=note_request.source_passage,
        content_type=note_request.content_type,
        source_url=note_request.source_url,
        document_id=note_request.document_id,
        tags=note_request.tags
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@router.get("/notes", response_model=list[NoteResponse])
def get_notes(db = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(Note).join(Document).join(Source).where(Source.user_id == user.id)
    result = db.execute(statement)
    notes = result.scalars().all()
    return notes    

@router.get("/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    note = db.execute(select(Note).join(Document).join(Source).where(Note.id == note_id, Source.user_id == user.id)).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@router.delete("/notes/{note_id}", response_model=NoteResponse, dependencies=[Depends(require_csrf)])
def delete_note(note_id: int, db = Depends(get_db), user: User = Depends(get_current_user)):
    note = db.execute(select(Note).join(Document).join(Source).where(Note.id == note_id, Source.user_id == user.id)).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return note

@router.patch("/notes/{note_id}", response_model=NoteResponse, dependencies=[Depends(require_csrf)])
def update_note(note_id: int, note_request: NoteUpdateRequest, db = Depends(get_db), user: User = Depends(get_current_user)):
    note = db.execute(select(Note).join(Document).join(Source).where(Note.id == note_id, Source.user_id == user.id)).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    updates = note_request.model_dump(exclude_unset=True)
    if "document_id" in updates and not db.execute(select(Document).join(Source).where(Document.id == updates["document_id"], Source.user_id == user.id)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in updates.items():
        setattr(note, key, value)
    db.commit()
    db.refresh(note)
    return note
