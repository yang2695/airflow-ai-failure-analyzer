# Demo guide

This is a short walkthrough for showing the project in about one minute.

1. Start the app and open `http://localhost:8501`.
2. Click **Snowflake Authentication Error** and then **Analyze failure**.
3. Point out the failure type, severity, confidence, and the evidence panel.
4. Open **Airflow context parsed from this log** to show the DAG, task, run, and retry attempt were extracted from the log.
5. Show the recommended-action checklist and the retry guidance.
6. Click **Download incident report** to show how the result can become a shareable handoff.
7. Try **API Rate Limit** or **Out Of Memory Error** to show that the recommendation changes with the failure type.

Talking point: the current analyzer uses transparent rules. The `FailureAnalyzer` interface is the seam where an LLM can later help with unfamiliar or more complicated logs.
