import os
import json

import requests
import streamlit as st

API_URL = os.getenv("ANALYZER_API_URL", "http://localhost:8000/analyze")
SAMPLES = {
    "Snowflake Authentication Error": "dag_id=daily_revenue\ntask_id=load_snowflake\nrun_id=scheduled__2026-06-22\ntry_number=2\nERROR - Snowflake connection failed: Authentication failed for user AIRFLOW_SERVICE.",
    "S3 Access Denied": "dag_id=customer_events\ntask_id=read_raw_events\nrun_id=manual__2026-06-22\ntry_number=1\nERROR - An error occurred (AccessDenied) when calling GetObject: Access Denied. s3://analytics-raw/events.json",
    "Database Timeout": "dag_id=warehouse_sync\ntask_id=upsert_postgres\ntry_number=3\nERROR - psycopg2.OperationalError: could not connect to server: Connection timed out. Database unavailable.",
    "Out Of Memory Error": "dag_id=large_backfill\ntask_id=transform_partition\ntry_number=1\nERROR - Container terminated with exit code 137. OOMKilled: task process exceeded memory limit.",
    "Python Traceback": "dag_id=customer_dimensions\ntask_id=validate_records\ntry_number=1\nERROR - Task failed with exception\nTraceback (most recent call last):\nKeyError: 'customer_id'",
    "Data Quality Failure": "dag_id=orders_pipeline\ntask_id=validate_order_records\ntry_number=1\nERROR - not null constraint violated: column customer_id contains a null value",
    "API Rate Limit": "dag_id=crm_sync\ntask_id=fetch_contacts\ntry_number=3\nERROR - HTTP 429 Too Many Requests: rate limit exceeded by external API",
    "Missing Dependency": "dag_id=monthly_metrics\ntask_id=build_report\ntry_number=1\nERROR - ModuleNotFoundError: No module named 'great_expectations'",
}

st.set_page_config(page_title="Airflow AI Failure Analyzer", page_icon="✦", layout="wide")
st.markdown("""<style>.block-container{max-width:1180px;padding-top:2.5rem}.hero{padding:1.8rem 2rem;border-radius:18px;color:#f8fafc;background:linear-gradient(120deg,#0f172a,#0c4a6e);margin-bottom:1.5rem}.hero h1{margin:0;font-size:2.25rem}.hero p{color:#cbd5e1;margin-bottom:0}.card{border:1px solid #e2e8f0;background:#fff;border-radius:14px;padding:1.1rem 1.25rem;min-height:116px;box-shadow:0 2px 5px rgba(15,23,42,.04)}.eyebrow{color:#64748b;font-size:.78rem;letter-spacing:.08em;font-weight:700;text-transform:uppercase}.value{color:#0f172a;font-size:1.15rem;font-weight:700;margin-top:.35rem}.confidence{color:#0369a1;font-weight:700}</style>""", unsafe_allow_html=True)
st.markdown("""<div class="hero"><h1>Airflow AI Failure Analyzer</h1><p>Turn noisy task logs into a clear diagnosis, impact assessment, and next action.</p></div>""", unsafe_allow_html=True)
if "log_text" not in st.session_state:
    st.session_state.log_text = SAMPLES["Snowflake Authentication Error"]
if "history" not in st.session_state:
    st.session_state.history = []
if "action_version" not in st.session_state:
    st.session_state.action_version = 0

with st.sidebar:
    st.header("Session history")
    st.caption("Recent analyses stay in this browser session only.")
    for item in st.session_state.history[:5]:
        st.write(f"**{item['failure_type']}** · {item['severity']}")
    if st.session_state.history and st.button("Clear history"):
        st.session_state.history = []
        st.rerun()
    st.divider()
    st.subheader("Analyzer coverage")
    st.caption("Database, Snowflake, S3, resources, data quality, APIs, configuration, and Python errors.")
    st.info("Paste only logs you are allowed to share. The app flags text that looks like a credential or secret.")
st.markdown("#### Try a sample failure")
sample_items = list(SAMPLES.items())
for start in range(0, len(sample_items), 4):
    for column, (label, text) in zip(st.columns(4), sample_items[start:start + 4]):
        if column.button(label, use_container_width=True):
            st.session_state.log_text = text
st.markdown("#### Paste Airflow task logs")
log_text = st.text_area("Paste an Airflow task log", key="log_text", height=265, label_visibility="collapsed")
if st.button("Analyze failure", type="primary", use_container_width=True):
    if not log_text.strip():
        st.warning("Paste a task log before running an analysis.")
    else:
        try:
            response = requests.post(API_URL, json={"log_text": log_text}, timeout=10)
            response.raise_for_status()
            st.session_state.analysis = response.json()
            st.session_state.history.insert(0, st.session_state.analysis)
            st.session_state.history = st.session_state.history[:5]
            st.session_state.action_version += 1
        except requests.RequestException as error:
            st.error(f"Could not reach the analysis API. Start the FastAPI backend first. ({error})")
if analysis := st.session_state.get("analysis"):
    st.markdown("### Analysis result")
    for column, label, value in zip(st.columns(3), ["Failure type", "Severity", "Confidence"], [analysis["failure_type"], analysis["severity"], f"{analysis['confidence']}%"]):
        column.markdown(f'<div class="card"><div class="eyebrow">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    for column, label, value in zip(st.columns(2), ["Root cause", "Summary"], [analysis["root_cause"], analysis["summary"]]):
        column.markdown(f'<div class="card"><div class="eyebrow">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)
    st.info(analysis["incident_summary"])
    profile = analysis["log_profile"]
    profile_columns = st.columns(3)
    profile_columns[0].metric("Error lines", profile["error_lines"])
    profile_columns[1].metric("Warning lines", profile["warning_lines"])
    profile_columns[2].metric("First timestamp", profile["first_timestamp"] or "Not found")
    context = analysis["airflow_context"]
    with st.expander("Airflow context parsed from this log"):
        context_columns = st.columns(4)
        for column, label, value in zip(context_columns, ["DAG", "Task", "Run", "Attempt"], [context["dag_id"] or "Not found", context["task_id"] or "Not found", context["run_id"] or "Not found", str(context["try_number"] or "Not found")]):
            column.metric(label, value)
        st.caption(f"Parsed {context['log_line_count']} log line(s).")
    st.markdown("#### Recommended actions")
    for index, action in enumerate(analysis["recommended_actions"]):
        st.checkbox(action, key=f"action_{st.session_state.action_version}_{index}")
    st.markdown("#### Retry guidance")
    st.write(analysis["retry_guidance"])
    if analysis["matched_indicators"]:
        st.caption("Matched indicators: " + ", ".join(f"`{item}`" for item in analysis["matched_indicators"]))
    if analysis["secondary_signals"]:
        st.warning("Other signals found: " + ", ".join(analysis["secondary_signals"]))
    if analysis["risk_flags"]:
        st.markdown("#### Review before sharing or retrying")
        for flag in analysis["risk_flags"]:
            st.warning(flag)
    with st.expander("Evidence found in the log"):
        if analysis["evidence"]:
            st.code("\n".join(analysis["evidence"]), language="text")
        else:
            st.write("No specific evidence lines were identified for this result.")
    report = f"# Airflow Failure Report\n\n{analysis['incident_summary']}\n\n## Root cause\n{analysis['root_cause']}\n\n## Recommended actions\n" + "\n".join(f"- {action}" for action in analysis["recommended_actions"])
    download_columns = st.columns(2)
    download_columns[0].download_button("Download analysis as JSON", data=json.dumps(analysis, indent=2), file_name="airflow-failure-analysis.json", mime="application/json")
    download_columns[1].download_button("Download incident report", data=report, file_name="airflow-failure-report.md", mime="text/markdown")
