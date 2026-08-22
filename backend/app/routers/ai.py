from app.services.anthropic_service import simplify_text
from app.services.anthropic_service import explain_text
from app.services.anthropic_service import summarize_text
from app.schemas.ai import SimplifyRequest, ExplanationRequest, SummarizeRequest
from app.services.usage_service import check_and_increment
from fastapi import APIRouter

router = APIRouter()

@router.post("/simplify")
def simplify(request: SimplifyRequest):
    check_and_increment(request.install_id)

    result = simplify_text(request.text, 
                           request.target_grade_level,
                           request.target_length)
   
    return {"simplified": result}

@router.post("/explain")
def explain(request: ExplanationRequest):
    check_and_increment(request.install_id)

    result = explain_text(request.text,
                          request.context,
                          request.target_grade_level,
                          request.target_length)

    return {"explanation" : result}

@router.post("/summarize")
def summarize(request: SummarizeRequest):
    check_and_increment(request.install_id)

    result = summarize_text(request.text,
                            request.target_grade_level,
                            request.target_length)

    return {"summary": result}
