from pydantic import BaseModel, ConfigDict
from datetime import datetime

class SourceCreateRequest(BaseModel):
    type: str
    url: str | None = None

class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    url: str | None = None
    created_at: datetime

class SourceUpdateRequest(BaseModel):
    type: str | None = None
    url: str | None = None
