from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    log_text: str = Field(..., min_length=1)


class AirflowContext(BaseModel):
    """Useful execution details parsed from a task log when available."""

    dag_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    try_number: int | None = None
    log_line_count: int


class LogProfile(BaseModel):
    """Operational signals measured directly from the pasted log."""

    error_lines: int
    warning_lines: int
    first_timestamp: str | None = None


class AnalysisResponse(BaseModel):
    """Structured result returned by every analyzer implementation."""

    failure_type: str
    severity: str
    summary: str
    root_cause: str
    recommended_actions: list[str]
    confidence: int = Field(..., ge=0, le=100)
    match_factors: list[str]
    matched_indicators: list[str]
    evidence: list[str]
    secondary_signals: list[str]
    airflow_context: AirflowContext
    incident_summary: str
    retry_guidance: str
    risk_flags: list[str]
    log_profile: LogProfile
    exception_name: str | None = None
    failure_fingerprint: str
