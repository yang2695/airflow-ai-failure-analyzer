"""Replace RuleBasedFailureAnalyzer with an OpenAI/Anthropic implementation later."""

from abc import ABC, abstractmethod

from backend.schemas import AnalysisResponse


class FailureAnalyzer(ABC):
    @abstractmethod
    def analyze(self, log_text: str) -> AnalysisResponse:
        """Return a structured diagnosis for an Airflow task log."""


class RuleBasedFailureAnalyzer(FailureAnalyzer):
    RULES = (
        (("out of memory", "oom", "killed process"), "Resource Exhaustion", "Critical", "The task was terminated because its runtime ran out of memory.", "The worker, container, or process exceeded its available memory limit.", ["Increase the task or worker memory allocation.", "Process data in smaller batches and release large intermediate objects.", "Review task memory metrics to size the workload appropriately."]),
        (("snowflake", "warehouse", "authentication failed"), "Snowflake Failure", "High", "The task failed while connecting to or running work in Snowflake.", "Snowflake credentials, warehouse availability, or account configuration prevented execution.", ["Verify the Airflow Snowflake connection credentials and account URL.", "Confirm the configured warehouse is running and the role has required privileges.", "Rotate expired credentials or update the connection secret if needed."]),
        (("connection refused", "timeout", "could not connect", "database unavailable"), "Database Connectivity", "High", "The task could not establish a reliable connection to its database.", "The database endpoint was unreachable, slow to respond, or unavailable.", ["Check database health, endpoint reachability, and network policies.", "Validate the Airflow connection host, port, and credentials.", "Add retries with backoff after resolving availability issues."]),
        (("s3", "access denied", "no such key"), "S3 Failure", "Medium", "The task could not access the required object or bucket in Amazon S3.", "The object path is missing or the task's IAM identity lacks S3 permissions.", ["Verify the bucket name, object key, and upstream data delivery.", "Review the task role's s3:GetObject and s3:ListBucket permissions.", "Confirm bucket and KMS policies allow this workload."]),
        (("traceback", "valueerror", "keyerror", "typeerror"), "Application Error", "Medium", "The task raised an unhandled Python exception.", "Application code encountered invalid data, a missing value, or an unexpected type.", ["Inspect the final traceback frames and failing line of task code.", "Validate input data and handle expected edge cases.", "Add a regression test before deploying the fix."]),
    )

    def analyze(self, log_text: str) -> AnalysisResponse:
        text = log_text.lower()
        for keywords, failure_type, severity, summary, root_cause, actions in self.RULES:
            if any(keyword in text for keyword in keywords):
                return AnalysisResponse(failure_type=failure_type, severity=severity, summary=summary, root_cause=root_cause, recommended_actions=actions)
        # Future LLM integration point: call OpenAI or Anthropic here, validate its
        # structured response, and return the same AnalysisResponse contract.
        return AnalysisResponse(failure_type="Unknown", severity="Medium", summary="The log does not match a supported failure pattern yet.", root_cause="No recognized signature was found in the provided task log.", recommended_actions=["Review the final error lines and surrounding task context.", "Check upstream task status, connections, and recent deployment changes.", "Add this signature to the analyzer rules or route it to an LLM reviewer."])


analyzer = RuleBasedFailureAnalyzer()
