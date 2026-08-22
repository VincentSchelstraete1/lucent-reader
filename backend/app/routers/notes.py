from fastapi import APIRouter, Depends, HTTPException
from app.schemas.note import NoteCreateRequest, NoteResponse, NoteUpdateRequest
from app.database import get_db
from app.models.note import Note
from sqlalchemy import select
router = APIRouter()

@router.post("/notes", response_model=NoteResponse)
def create_note(note_request: NoteCreateRequest, db = Depends(get_db)):
    note = Note(
        title=note_request.title,
        content=note_request.content,
        content_type=note_request.content_type,
        source_url=note_request.source_url,
        document_id=note_request.document_id
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@router.get("/notes", response_model=list[NoteResponse])
def get_notes(db = Depends(get_db)):
    statement = select(Note)
    result = db.execute(statement)
    notes = result.scalars().all()
    return notes    

@router.get("/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@router.delete("/notes/{note_id}", response_model=NoteResponse)
def delete_note(note_id: int, db = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return note

@router.patch("/notes/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, note_request: NoteUpdateRequest, db = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    updates = note_request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(note, key, value)
    db.commit()
    db.refresh(note)
    return note