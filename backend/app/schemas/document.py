from pydantic import BaseModel, ConfigDict
from datetime import datetime

class DocumentCreateRequest(BaseModel):
    source_id: int
    title: str
    content: str

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
