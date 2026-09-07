from pydantic import BaseModel, ConfigDict, Field
from .schema import LearningObject
from app.routing import RepresentationDecision
from app.segmentation import LearningBlock
from .teaching import TeachingPlan

class GeneratedNoteSection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    learning_block_id: str = Field(alias="learningBlockId")
    title: str | None = None
    source: dict
    representation_decision: dict = Field(alias="representationDecision")
    learning_object: LearningObject = Field(alias="learningObject")
    generation_fallback: bool = Field(default=False, alias="generationFallback")
    teaching_plan: TeachingPlan | None = Field(default=None, alias="teachingPlan")

class GeneratedNote(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    source_document: dict = Field(alias="sourceDocument")
    title: str
    sections: list[GeneratedNoteSection]

def assemble_note(filename: str, source_type: str, page_count: int, blocks: list[LearningBlock], decisions: dict[str, RepresentationDecision], objects: dict[str, LearningObject], plans: dict[str, TeachingPlan] | None = None) -> GeneratedNote:
    def source_dict(source):
        return {"page_start": source.page_start, "page_end": source.page_end, "raw_block_ids": source.raw_block_ids, "bboxes": source.bboxes, "locations": [{"kind": x.kind, "index": x.index, "sequence_id": x.sequence_id} for x in source.locations]}
    return GeneratedNote(sourceDocument={"filename": filename, "sourceType": source_type, "pageCount": page_count}, title=filename.rsplit(".", 1)[0], sections=[GeneratedNoteSection(learningBlockId=b.id, title=b.title, source=source_dict(b.source), representationDecision=decisions[b.id].__dict__, learningObject=objects[b.id], generationFallback=objects[b.id].type != decisions[b.id].type, teachingPlan=(plans or {}).get(b.id)) for b in blocks if b.id in objects])
