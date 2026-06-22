from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    log_text: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    failure_type: str
    severity: str
    summary: str
    root_cause: str
    recommended_actions: list[str]
