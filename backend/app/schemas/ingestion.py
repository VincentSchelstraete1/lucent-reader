from typing import Literal

from pydantic import BaseModel


class PdfIngestionResponse(BaseModel):
    status: Literal["success"]
    original_filename: str
    source_type: Literal["pdf"]
    markdown: str
    extracted_character_count: int
