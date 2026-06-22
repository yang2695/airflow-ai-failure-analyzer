from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    log_text: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    """Structured result returned by every analyzer implementation."""

    failure_type: str
    severity: str
    summary: str
    root_cause: str
    recommended_actions: list[str]
    confidence: int = Field(..., ge=0, le=100)
    matched_indicators: list[str]
    evidence: list[str]
