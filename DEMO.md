# Demo guide

This is a short walkthrough for showing the project.

1. Start the app and open `http://localhost:8501`.
2. Click **Snowflake Authentication Error** and then **Check log**.
3. Point out the failure type, severity, match strength, and matched lines.
4. Open **Task details found in this log** to show the DAG, task, run, and retry attempt were extracted from the log.
5. Show the checklist and the retry note.
6. Click **Download incident report** to show how the result can become a shareable handoff.
7. Try **API Rate Limit** or **Out Of Memory Error** to show that the recommendation changes with the failure type.

Talking point: the current analyzer uses rules, so each result points back to words in the log.
