"""Transparent, evidence-based Airflow log diagnosis.

An OpenAI or Anthropic implementation can later satisfy the same FailureAnalyzer
interface and return the same AnalysisResponse model.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re

from backend.schemas import AirflowContext, AnalysisResponse


class FailureAnalyzer(ABC):
    @abstractmethod
    def analyze(self, log_text: str) -> AnalysisResponse:
        """Return a structured diagnosis for an Airflow task log."""


@dataclass(frozen=True)
class FailureRule:
    """A single explainable detection rule."""

    keywords: tuple[str, ...]
    failure_type: str
    severity: str
    summary: str
    root_cause: str
    recommended_actions: list[str]


class RuleBasedFailureAnalyzer(FailureAnalyzer):
    """Scores known failure signatures and returns the strongest match."""

    RULES = (
        FailureRule(("out of memory", "oom", "killed process"), "Resource Exhaustion", "Critical", "The task was terminated because its runtime ran out of memory.", "The worker, container, or process exceeded its available memory limit.", ["Increase the task or worker memory allocation.", "Process data in smaller batches and release large intermediate objects.", "Review task memory metrics to size the workload appropriately."]),
        FailureRule(("snowflake", "warehouse", "authentication failed"), "Snowflake Failure", "High", "The task failed while connecting to or running work in Snowflake.", "Snowflake credentials, warehouse availability, or account configuration prevented execution.", ["Verify the Airflow Snowflake connection credentials and account URL.", "Confirm the configured warehouse is running and the role has required privileges.", "Rotate expired credentials or update the connection secret if needed."]),
        FailureRule(("connection refused", "timeout", "could not connect", "database unavailable"), "Database Connectivity", "High", "The task could not establish a reliable connection to its database.", "The database endpoint was unreachable, slow to respond, or unavailable.", ["Check database health, endpoint reachability, and network policies.", "Validate the Airflow connection host, port, and credentials.", "Add retries with backoff after resolving availability issues."]),
        FailureRule(("s3", "access denied", "no such key"), "S3 Failure", "Medium", "The task could not access the required object or bucket in Amazon S3.", "The object path is missing or the task's IAM identity lacks S3 permissions.", ["Verify the bucket name, object key, and upstream data delivery.", "Review the task role's s3:GetObject and s3:ListBucket permissions.", "Confirm bucket and KMS policies allow this workload."]),
        FailureRule(("traceback", "valueerror", "keyerror", "typeerror"), "Application Error", "Medium", "The task raised an unhandled Python exception.", "Application code encountered invalid data, a missing value, or an unexpected type.", ["Inspect the final traceback frames and failing line of task code.", "Validate input data and handle expected edge cases.", "Add a regression test before deploying the fix."]),
    )

    def analyze(self, log_text: str) -> AnalysisResponse:
        normalized_text = log_text.lower()
        matches = [
            (rule, [keyword for keyword in rule.keywords if keyword in normalized_text])
            for rule in self.RULES
        ]
        matches = [(rule, indicators) for rule, indicators in matches if indicators]

        if not matches:
            return self._unknown_result()

        # More matching indicators beat a broad one-keyword match. Rule order
        # breaks ties, preserving the intentional priority of critical errors.
        rule, indicators = max(matches, key=lambda item: len(item[1]))
        confidence = min(95, 62 + (len(indicators) - 1) * 16)
        context = self._extract_airflow_context(log_text)
        return AnalysisResponse(
            failure_type=rule.failure_type,
            severity=rule.severity,
            summary=rule.summary,
            root_cause=rule.root_cause,
            recommended_actions=rule.recommended_actions,
            confidence=confidence,
            matched_indicators=indicators,
            evidence=self._evidence_lines(log_text, indicators),
            secondary_signals=[candidate.failure_type for candidate, _ in matches if candidate != rule],
            airflow_context=context,
            incident_summary=self._incident_summary(rule, context),
        )

    @staticmethod
    def _evidence_lines(log_text: str, indicators: list[str]) -> list[str]:
        """Return up to three log lines that visibly support the diagnosis."""
        lines = log_text.splitlines() or [log_text]
        context_pattern = r"^\s*(dag_id|task_id|run_id|try_number)\s*="
        evidence = [
            line.strip()
            for line in lines
            if not re.match(context_pattern, line, flags=re.IGNORECASE)
            and any(word in line.lower() for word in indicators)
        ]
        return evidence[:3]

    @staticmethod
    def _extract_airflow_context(log_text: str) -> AirflowContext:
        """Pull commonly available task metadata from Airflow-style log lines."""
        def find(pattern: str) -> str | None:
            match = re.search(pattern, log_text, flags=re.IGNORECASE)
            return match.group(1) if match else None

        try_number = find(r"(?:try_number|attempt)\s*[=:]\s*(\d+)")
        return AirflowContext(
            dag_id=find(r"(?:dag_id|dag)\s*[=:]\s*([\w.-]+)"),
            task_id=find(r"(?:task_id|task)\s*[=:]\s*([\w.-]+)"),
            run_id=find(r"run_id\s*[=:]\s*([^\s,]+)"),
            try_number=int(try_number) if try_number else None,
            log_line_count=len(log_text.splitlines()) or 1,
        )

    @staticmethod
    def _incident_summary(rule: FailureRule, context: AirflowContext) -> str:
        """Create a short status-update sentence that can be pasted into an incident."""
        task = f"task `{context.task_id}`" if context.task_id else "an Airflow task"
        dag = f" in DAG `{context.dag_id}`" if context.dag_id else ""
        retry = f" on attempt {context.try_number}" if context.try_number else ""
        return f"{rule.severity} {rule.failure_type} detected for {task}{dag}{retry}."

    @staticmethod
    def _unknown_result() -> AnalysisResponse:
        # LLM integration point: submit the raw log here and validate its output.
        return AnalysisResponse(
            failure_type="Unknown",
            severity="Medium",
            summary="The log does not match a supported failure pattern yet.",
            root_cause="No recognized signature was found in the provided task log.",
            recommended_actions=["Review the final error lines and surrounding task context.", "Check upstream task status, connections, and recent deployment changes.", "Add this signature to the analyzer rules or route it to an LLM reviewer."],
            confidence=20,
            matched_indicators=[],
            evidence=[],
            secondary_signals=[],
            airflow_context=AirflowContext(log_line_count=1),
            incident_summary="An Airflow task failed, but no known failure signature was detected.",
        )


analyzer = RuleBasedFailureAnalyzer()
