"""Airflow log triage using simple, inspectable rules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import re

from backend.schemas import AirflowContext, AnalysisResponse, LogProfile


class FailureAnalyzer(ABC):
    @abstractmethod
    def analyze(self, log_text: str) -> AnalysisResponse:
        """Return a result for one Airflow task log."""


@dataclass(frozen=True)
class FailureRule:
    """One known failure pattern."""

    keywords: tuple[str, ...]
    failure_type: str
    severity: str
    summary: str
    root_cause: str
    recommended_actions: list[str]


class RuleBasedFailureAnalyzer(FailureAnalyzer):
    """Checks logs against known failure patterns."""

    RULES = (
        FailureRule(("out of memory", "oom", "killed process"), "Resource Exhaustion", "Critical", "The task was terminated because its runtime ran out of memory.", "The worker, container, or process exceeded its available memory limit.", ["Increase the task or worker memory allocation.", "Process data in smaller batches and release large intermediate objects.", "Review task memory metrics to size the workload appropriately."]),
        FailureRule(("snowflake", "warehouse", "authentication failed"), "Snowflake Failure", "High", "The task failed while connecting to or running work in Snowflake.", "Snowflake credentials, warehouse availability, or account configuration prevented execution.", ["Verify the Airflow Snowflake connection credentials and account URL.", "Confirm the configured warehouse is running and the role has required privileges.", "Rotate expired credentials or update the connection secret if needed."]),
        FailureRule(("connection refused", "timeout", "could not connect", "database unavailable"), "Database Connectivity", "High", "The task could not establish a reliable connection to its database.", "The database endpoint was unreachable, slow to respond, or unavailable.", ["Check database health, endpoint reachability, and network policies.", "Validate the Airflow connection host, port, and credentials.", "Add retries with backoff after resolving availability issues."]),
        FailureRule(("s3", "access denied", "no such key"), "S3 Failure", "Medium", "The task could not access the required object or bucket in Amazon S3.", "The object path is missing or the task's IAM identity lacks S3 permissions.", ["Verify the bucket name, object key, and upstream data delivery.", "Review the task role's s3:GetObject and s3:ListBucket permissions.", "Confirm bucket and KMS policies allow this workload."]),
        FailureRule(("schema mismatch", "not null constraint", "duplicate key", "null value"), "Data Quality Failure", "Medium", "The task failed because incoming data did not satisfy an expected quality or schema rule.", "A source record is missing a required value, violates a uniqueness constraint, or no longer matches the expected schema.", ["Identify the source records that violate the expectation.", "Confirm whether the upstream schema or data contract changed.", "Decide whether the task should quarantine, correct, or reject invalid records."]),
        FailureRule(("http 429", "rate limit", "too many requests", "service unavailable", "http 500"), "External Service Failure", "High", "The task failed while calling an external service or API.", "The downstream service was rate-limiting requests, unavailable, or returning a server-side error.", ["Check the downstream service status and recent error rates.", "Use exponential backoff and respect the provider's rate-limit headers.", "Make the task idempotent before retrying it."]),
        FailureRule(("modulenotfounderror", "importerror", "invalid configuration", "airflowexception"), "Configuration Failure", "Medium", "The task could not start because its runtime configuration or dependency setup is invalid.", "A required package, import, Airflow setting, or deployment configuration is missing or incorrect.", ["Compare the deployment image and requirements with the working environment.", "Check recent environment-variable and connection changes.", "Validate the DAG imports before deploying again."]),
        FailureRule(("crashloopbackoff", "imagepullbackoff", "pod evicted", "evicted"), "Kubernetes Workload Failure", "High", "The task's Kubernetes workload did not start or was removed before it could finish.", "The pod may be restarting, unable to pull its image, or removed because the cluster ran out of a required resource.", ["Check the pod events and container status in the Kubernetes cluster.", "Verify the image reference and registry permissions.", "Review node capacity and the task's CPU and memory requests."]),
        FailureRule(("no space left on device", "disk quota exceeded", "read-only file system"), "Storage Failure", "High", "The task could not write to the required filesystem or storage volume.", "The target volume is full, over quota, or mounted read-only.", ["Check available disk space and volume quotas.", "Remove temporary files or move the workload to a larger volume.", "Confirm that the worker can write to the target path."]),
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
            return self._unknown_result(log_text)

        # More matched indicators win. Rule order breaks a tie.
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
            retry_guidance=self._retry_guidance(rule.severity, context.try_number),
            risk_flags=self._risk_flags(log_text, rule.severity, context.try_number),
            log_profile=self._log_profile(log_text),
            exception_name=self._exception_name(log_text),
            failure_fingerprint=self._fingerprint(rule.failure_type, indicators),
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
    def _retry_guidance(severity: str, try_number: int | None) -> str:
        if severity == "Critical":
            return "Do not retry until the resource limit or workload size has been addressed."
        if try_number and try_number >= 3:
            return "This task has retried several times. Investigate before allowing another automatic retry."
        if severity == "High":
            return "Retry only after verifying the downstream service or connection has recovered."
        return "Correct the underlying issue, then retry this task instance once."

    @staticmethod
    def _risk_flags(log_text: str, severity: str, try_number: int | None) -> list[str]:
        flags = []
        if re.search(r"password\s*=|secret|token\s*=|aws_secret_access_key|private_key", log_text, re.IGNORECASE):
            flags.append("Potential credential or secret detected. Avoid sharing this raw log outside an approved environment.")
        if severity == "Critical":
            flags.append("Critical failure: check capacity and downstream impact before rerunning dependent tasks.")
        if try_number and try_number >= 3:
            flags.append("Multiple retries detected. Further retries may add load without resolving the underlying issue.")
        return flags

    @staticmethod
    def _log_profile(log_text: str) -> LogProfile:
        lines = log_text.splitlines() or [log_text]
        first_timestamp = re.search(r"\[(\d{4}-\d{2}-\d{2}[^\]]*)\]", log_text)
        return LogProfile(
            error_lines=sum("error" in line.lower() or "exception" in line.lower() for line in lines),
            warning_lines=sum("warn" in line.lower() for line in lines),
            first_timestamp=first_timestamp.group(1) if first_timestamp else None,
        )

    @staticmethod
    def _exception_name(log_text: str) -> str | None:
        match = re.search(r"\b([\w.]*(?:Error|Exception|Killed))(?::|\b)", log_text)
        return match.group(1).split(".")[-1] if match else None

    @staticmethod
    def _fingerprint(failure_type: str, indicators: list[str]) -> str:
        source = "|".join([failure_type, *sorted(indicators)])
        return hashlib.sha256(source.encode()).hexdigest()[:10]

    @staticmethod
    def _unknown_result(log_text: str) -> AnalysisResponse:
        return AnalysisResponse(
            failure_type="Unknown",
            severity="Medium",
            summary="The log does not match a supported failure pattern yet.",
            root_cause="No recognized signature was found in the provided task log.",
            recommended_actions=["Review the final error lines and surrounding task context.", "Check upstream task status, connections, and recent deployment changes.", "Add the pattern to the rule set if it appears again."],
            confidence=20,
            matched_indicators=[],
            evidence=[],
            secondary_signals=[],
            airflow_context=RuleBasedFailureAnalyzer._extract_airflow_context(log_text),
            incident_summary="An Airflow task failed, but no known failure signature was detected.",
            retry_guidance="Avoid blind retries. Review the final error lines and surrounding task context first.",
            risk_flags=[],
            log_profile=RuleBasedFailureAnalyzer._log_profile(log_text),
            exception_name=RuleBasedFailureAnalyzer._exception_name(log_text),
            failure_fingerprint="unknown",
        )


analyzer = RuleBasedFailureAnalyzer()
