from pydantic import BaseModel, ConfigDict
from datetime import datetime

class NoteCreateRequest(BaseModel):
    title: str
    content: str
    content_type: str
    source_url: str | None = None

class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    content_type: str
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime