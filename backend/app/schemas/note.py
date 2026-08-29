from pydantic import BaseModel, ConfigDict
from datetime import datetime

class NoteCreateRequest(BaseModel):
    title: str
    content: str
    content_type: str
    source_url: str | None = None
    document_id: int
    tags: list[str] | None = None

class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    content_type: str
    source_url: str | None = None
    document_id: int | None = None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime

class NoteUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    content_type: str | None = None
    source_url: str | None = None
    document_id: int | None = None
    tags: list[str] | None = None
