"""Temporary local QA entry point for exercising the real ingestion pipeline.

This script is intentionally not an API or product surface. It lets browser QA
seed a completed note when the automated browser cannot drive a native file
picker. The resulting records use the same persistence helper as an upload.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.ingestion import MarkItDownAdapter, PdfDocumentIngestor, PyMuPDFPageExtractor
from app.models.auth import User
from app.models.document import Document
from app.models.note import Note
from app.models.source import Source
from app.normalization import normalize_document
from app.routers.ingestion import _generate_outputs, _persist_learning_note, _segment_and_route
from app.routing import ClassifierAdapter
from app.schemas.ingestion import PdfIngestionResponse
from app.segmentation import segment_document
from app.semantic import (
    AnthropicSemanticGenerator,
    DeterministicSemanticGenerator,
    HybridSemanticGenerator,
    PedagogicalPlanner,
    SectionNote,
    assemble_note,
    generate_sections_concurrently,
    group_learning_blocks,
    is_low_value_section,
)


class NoOpinionClassifier(ClassifierAdapter):
    def classify(self, text: str):
        return None


async def main(path: Path, email: str, only: list[int]) -> None:
    extracted = PdfDocumentIngestor(PyMuPDFPageExtractor(), MarkItDownAdapter()).ingest_pdf(
        path.read_bytes(), filename=path.name
    )
    normalized = normalize_document(extracted)
    blocks, decisions = _segment_and_route(normalized, NoOpinionClassifier())
    generator = HybridSemanticGenerator(AnthropicSemanticGenerator(), planner=PedagogicalPlanner())
    if only:
        deterministic_objects = {block.id: DeterministicSemanticGenerator().generate(block, decisions[block.id]) for block in blocks}
        generated_note = assemble_note(extracted.filename, extracted.source_type, extracted.page_count, blocks, decisions, deterministic_objects)
        sections = [section for section in group_learning_blocks(blocks) if not is_low_value_section(section)]
        selected = [section for index, section in enumerate(sections) if index in only]
        section_notes = await generate_sections_concurrently(selected, deterministic_objects, concurrency=3, use_model=True)
    else:
        generated_note, section_notes = await _generate_outputs(extracted, blocks, decisions, generator)
    response = PdfIngestionResponse.from_pipeline(
        extracted, normalized, blocks, decisions, generated_note, section_notes
    )
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        if only:
            source_key = f"{response.source_type}:{response.filename}"[:255]
            stored = db.execute(
                select(Note).join(Document).join(Source).where(
                    Source.user_id == user.id,
                    Source.type == "upload",
                    Source.url == source_key,
                    Note.content_type == "section_note",
                )
            ).scalars().first()
            if stored:
                import json
                existing = [SectionNote.model_validate(item) for item in json.loads(stored.content).get("sectionNotes", [])]
                replacements = {note.id: note for note in section_notes}
                response = response.model_copy(update={"section_notes": [replacements.get(note.id, note) for note in existing]})
        response = _persist_learning_note(db, user_id=user.id, response=response)
    print({
        "filename": response.filename,
        "learning_blocks": len(response.learning_blocks),
        "sections": len(response.section_notes),
        "component_kinds": [[component.kind for component in note.components] for note in response.section_notes],
        "document_id": response.document_id,
        "note_id": response.note_id,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--only", default="", help="Comma-separated eligible section indexes to regenerate and merge")
    args = parser.parse_args()
    asyncio.run(main(args.path, args.user_email, [int(value) for value in args.only.split(",") if value]))
