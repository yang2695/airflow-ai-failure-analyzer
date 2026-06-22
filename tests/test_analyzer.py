import pytest
from backend.analyzer import RuleBasedFailureAnalyzer


@pytest.mark.parametrize(("log", "category", "severity"), [
    ("connection refused", "Database Connectivity", "High"), ("snowflake authentication failed", "Snowflake Failure", "High"),
    ("s3 access denied", "S3 Failure", "Medium"), ("out of memory oom", "Resource Exhaustion", "Critical"),
    ("Traceback: KeyError", "Application Error", "Medium"), ("unfamiliar message", "Unknown", "Medium"),
    ("not null constraint violated", "Data Quality Failure", "Medium"),
    ("HTTP 429 rate limit exceeded", "External Service Failure", "High"),
    ("ModuleNotFoundError: missing package", "Configuration Failure", "Medium"),
])
def test_categories(log, category, severity):
    result = RuleBasedFailureAnalyzer().analyze(log)
    assert (result.failure_type, result.severity) == (category, severity)


def test_multiple_indicators_increase_confidence_and_return_evidence():
    log = "ERROR snowflake authentication failed\nwarehouse ANALYTICS_WH is unavailable"
    result = RuleBasedFailureAnalyzer().analyze(log)
    assert result.failure_type == "Snowflake Failure"
    assert result.confidence == 94
    assert result.matched_indicators == ["snowflake", "warehouse", "authentication failed"]
    assert result.evidence == ["ERROR snowflake authentication failed", "warehouse ANALYTICS_WH is unavailable"]


def test_unknown_result_has_low_confidence_and_no_evidence():
    result = RuleBasedFailureAnalyzer().analyze("A completely unfamiliar task message")
    assert result.confidence == 20
    assert result.matched_indicators == []
    assert result.evidence == []


def test_extracts_airflow_context_and_incident_summary():
    log = "dag_id=hourly_orders\ntask_id=load_s3\nrun_id=manual__2026-06-22\ntry_number=3\nERROR: s3 access denied"
    result = RuleBasedFailureAnalyzer().analyze(log)
    assert result.airflow_context.dag_id == "hourly_orders"
    assert result.airflow_context.task_id == "load_s3"
    assert result.airflow_context.run_id == "manual__2026-06-22"
    assert result.airflow_context.try_number == 3
    assert "task `load_s3` in DAG `hourly_orders` on attempt 3" in result.incident_summary


def test_exposes_secondary_signals_when_multiple_failure_types_match():
    result = RuleBasedFailureAnalyzer().analyze("snowflake authentication failed after database timeout")
    assert result.failure_type == "Snowflake Failure"
    assert result.secondary_signals == ["Database Connectivity"]


def test_profiles_log_and_flags_retries_and_sensitive_text():
    log = "[2026-06-22 10:00:00] WARN - retrying\nday_id=ignored\ntry_number=3\nERROR - OOMKilled. token=do-not-share"
    result = RuleBasedFailureAnalyzer().analyze(log)
    assert result.log_profile.error_lines == 1
    assert result.log_profile.warning_lines == 1
    assert result.log_profile.first_timestamp == "2026-06-22 10:00:00"
    assert len(result.risk_flags) == 3
    assert "Do not retry" in result.retry_guidance
