from pydantic import BaseModel, ConfigDict, model_validator
from datetime import datetime

class NoteCreateRequest(BaseModel):
    title: str
    content: str
    source_passage: str | None = None
    content_type: str
    source_url: str | None = None
    document_id: int
    tags: list[str] | None = None

    @model_validator(mode="after")
    def generated_results_require_source_passage(self):
        if self.content_type in {"explanation", "simplification"} and not self.source_passage:
            raise ValueError("Generated results require their originating source passage")
        return self

class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    source_passage: str | None = None
    content_type: str
    source_url: str | None = None
    document_id: int | None = None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime

class NoteUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    source_passage: str | None = None
    content_type: str | None = None
    source_url: str | None = None
    document_id: int | None = None
    tags: list[str] | None = None
