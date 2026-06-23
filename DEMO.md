# Demo guide

Use this as a short walkthrough when showing the project.

1. Start the app and open `http://localhost:8501`.
2. Click **Snowflake Authentication Error**, then click **Check log**.
3. Point out the failure type, the orange High severity card, and the match strength.
4. Open **How match strength is calculated** to show how the score was built from matching phrases and the error line.
5. Open **Task details found in this log** to show the DAG, task, run, and retry attempt pulled from the log.
6. Check an item under **What to check**. The progress bar shows how many items are complete.
7. Click **Download incident report**. Checked items are included in the report.
8. Click the Snowflake item in **Session history** to reopen the result.
9. Try **API Rate Limit**, **Kubernetes Pod Failure**, or **Disk Full** to show that the checks change with the problem.

The app uses rules and shows the matching lines, so someone can see why it picked a result.
