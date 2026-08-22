from pydantic import BaseModel

class NoteSection(BaseModel):
    heading: str
    content: str

class GeneratedNote(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    concepts: list[str]
    sections: list[NoteSection]
