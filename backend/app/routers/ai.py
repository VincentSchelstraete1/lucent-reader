from app.services.anthropic_service import simplify_text
from app.services.anthropic_service import explain_text
from app.services.anthropic_service import summarize_text
from app.schemas.ai import SimplifyRequest, ExplanationRequest, SummarizeRequest
from app.services.usage_service import check_and_increment
from fastapi import APIRouter, Depends
from app.auth_dependencies import get_current_user, require_csrf
from app.models.auth import User

router = APIRouter()

@router.post("/simplify", dependencies=[Depends(require_csrf)])
def simplify(request: SimplifyRequest, user: User = Depends(get_current_user)):
    check_and_increment(request.install_id)

    result = simplify_text(request.text, 
                           request.target_grade_level,
                           request.target_length)
   
    return {"simplified": result}

@router.post("/explain", dependencies=[Depends(require_csrf)])
def explain(request: ExplanationRequest, user: User = Depends(get_current_user)):
    check_and_increment(request.install_id)

    result = explain_text(request.text,
                          request.context,
                          request.target_grade_level,
                          request.target_length)

    return {"explanation" : result}

@router.post("/summarize", dependencies=[Depends(require_csrf)])
def summarize(request: SummarizeRequest, user: User = Depends(get_current_user)):
    check_and_increment(request.install_id)

    result = summarize_text(request.text,
                            request.target_grade_level,
                            request.target_length)

    return {"summary": result}
