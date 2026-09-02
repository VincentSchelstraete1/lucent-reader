from __future__ import annotations
import re
from pydantic import BaseModel, ConfigDict, Field
from app.segmentation import LearningBlock
from app.routing import RepresentationDecision

class ContextPacket(BaseModel):
    document_title: str | None = Field(default=None, alias="documentTitle")
    heading_ancestry: list[str] = Field(default_factory=list, alias="headingAncestry")
    previous_text: str | None = Field(default=None, alias="previousText")
    current_text: str = Field(alias="currentText")
    next_text: str | None = Field(default=None, alias="nextText")
    attached_context: list[str] = Field(default_factory=list, alias="attachedContext")

    model_config = ConfigDict(populate_by_name=True)

class TeachingPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    learning_goal: str = Field(alias="learningGoal")
    recommended_representation: str = Field(alias="recommendedRepresentation")
    final_representation: str = Field(alias="finalRepresentation")
    rationale: str
    core_ideas: list[str] = Field(default_factory=list, alias="coreIdeas")
    useful_context: list[str] = Field(default_factory=list, alias="usefulContext")
    omitted_noise: list[str] = Field(default_factory=list, alias="omittedNoise")
    representation_plan: list[str] = Field(default_factory=list, alias="representationPlan")
    context_packet: ContextPacket | None = Field(default=None, alias="contextPacket")
    override: bool = False

def build_context_packet(block: LearningBlock, *, previous: LearningBlock | None = None, next_block: LearningBlock | None = None, document_title: str | None = None) -> ContextPacket:
    clip = lambda value: value[:1200] if value else None
    attached = [f"table:{item}" for item in block.attached_table_ids] + [f"image:{item}" for item in block.attached_image_ids]
    return ContextPacket(documentTitle=document_title, headingAncestry=block.heading_ancestry, previousText=clip(previous.text if previous else None), currentText=block.text[:6000], nextText=clip(next_block.text if next_block else None), attachedContext=attached)

class DeterministicPedagogicalPlanner:
    def plan(self, block: LearningBlock, decision: RepresentationDecision, context: ContextPacket | None = None) -> TeachingPlan:
        text = block.text.strip()
        final = decision.type
        rationale = "Use the recommended representation because its structure is supported by the passage."
        ideas = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()][:4]
        plan: list[str] = []
        if decision.type == "concept_map":
            plan = ["Name the central concepts", "Label each relationship with its meaning", "Keep only source-grounded connections"]
            if not re.search(r"\b(caches?|maps?|contains?|uses?|depends on|involves)\b", text, re.I):
                final, rationale = "plain_text", "The router suggested a concept map, but the passage does not state reliable relationship labels."
        elif decision.type == "hierarchy": plan = ["Show the root category", "Preserve explicit parent-child containment", "Nest only relationships stated in the source"]
        elif decision.type == "quantitative": plan = ["State the formula", "Define variables and supplied values", "Show substitution, derivation, result, and interpretation"]
        elif decision.type == "causal": plan = ["Show direction", "Preserve intermediate effects", "Label the mechanism or change"]
        elif decision.type == "process": plan = ["Show ordered steps", "Explain what changes between steps", "Label meaningful transitions"]
        elif decision.type == "comparison": plan = ["Align shared dimensions", "Make differences and tradeoffs explicit"]
        else: plan = ["Give a concise explanation", "Retain key points and source-grounded definitions"]
        return TeachingPlan(learningGoal=f"Understand {block.title or 'the passage'}", recommendedRepresentation=decision.type, finalRepresentation=final, rationale=rationale, coreIdeas=ideas, usefulContext=context.heading_ancestry if context else [], representationPlan=plan, contextPacket=context, override=final != decision.type)
