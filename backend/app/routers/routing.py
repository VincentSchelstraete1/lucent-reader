from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth_dependencies import get_current_user, require_csrf
from app.models.auth import User
from app.routers.ingestion import get_classifier, get_semantic_generator
from app.routing import ClassifierAdapter, RepresentationDecision, route_learning_block_hybrid
from app.schemas.ingestion import RepresentationDecisionResponse
from app.semantic import SemanticGenerator, plain_text_fallback, build_context_packet
from app.normalization import SourceReference
from app.segmentation import LearningBlock, SegmentationMetadata

router = APIRouter(prefix="/routing")

class RoutingRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)

class RoutingResponse(BaseModel):
    decision: RepresentationDecisionResponse
    learning_object: dict
    teaching_plan: dict

def _canvas_learning_block(text: str) -> LearningBlock:
    """Build a complete LearningBlock for text with no document provenance."""
    return LearningBlock(
        id="learning-canvas",
        block_type="section",
        text=text,
        character_count=len(text),
        normalized_block_ids=[],
        source=SourceReference(page_start=None, page_end=None, raw_block_ids=[], bboxes=[], locations=[]),
        segmentation=SegmentationMetadata(method="canvas", boundary_reason="Interactive Learning Canvas input"),
        title=None,
        heading_ancestry=[],
        attached_table_ids=[],
        attached_image_ids=[],
        token_count=None,
    )

@router.post("/representation", response_model=RoutingResponse, dependencies=[Depends(require_csrf)])
def route_canvas_text(
    request: RoutingRequest,
    _user: User = Depends(get_current_user),
    classifier: ClassifierAdapter = Depends(get_classifier),
    semantic_generator: SemanticGenerator = Depends(get_semantic_generator),
) -> RoutingResponse:
    block = _canvas_learning_block(request.text.strip())
    decision: RepresentationDecision = route_learning_block_hybrid(block, classifier)
    plan = semantic_generator.plan(block, decision, build_context_packet(block))
    try:
        learning_object = semantic_generator.generate(block, decision, plan)
    except Exception:
        learning_object = plain_text_fallback(block)
    return RoutingResponse(
        decision=RepresentationDecisionResponse.from_decision(decision),
        learning_object=learning_object.model_dump(by_alias=True),
        teaching_plan=plan.model_dump(by_alias=True),
    )
