import pytest
from backend.analyzer import RuleBasedFailureAnalyzer


@pytest.mark.parametrize(("log", "category", "severity"), [
    ("connection refused", "Database Connectivity", "High"), ("snowflake authentication failed", "Snowflake Failure", "High"),
    ("s3 access denied", "S3 Failure", "Medium"), ("out of memory oom", "Resource Exhaustion", "Critical"),
    ("Traceback: KeyError", "Application Error", "Medium"), ("unfamiliar message", "Unknown", "Medium"),
])
def test_categories(log, category, severity):
    result = RuleBasedFailureAnalyzer().analyze(log)
    assert (result.failure_type, result.severity) == (category, severity)
