from pydantic import BaseModel

class SimplifyRequest(BaseModel):
    text: str
    target_grade_level: int
    target_length: str = "same"
    install_id: str

class ExplanationRequest(BaseModel):
    text: str 
    context: str 
    target_grade_level: int
    target_length: str = "same"
    install_id: str 
