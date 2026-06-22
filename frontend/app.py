import os

import requests
import streamlit as st

API_URL = os.getenv("ANALYZER_API_URL", "http://localhost:8000/analyze")
SAMPLES = {
    "Snowflake Authentication Error": "ERROR - Snowflake connection failed: Authentication failed for user AIRFLOW_SERVICE.",
    "S3 Access Denied": "ERROR - An error occurred (AccessDenied) when calling GetObject: Access Denied. s3://analytics-raw/events.json",
    "Database Timeout": "ERROR - psycopg2.OperationalError: could not connect to server: Connection timed out. Database unavailable.",
    "Out Of Memory Error": "ERROR - Container terminated with exit code 137. OOMKilled: task process exceeded memory limit.",
    "Python Traceback": "ERROR - Task failed with exception\nTraceback (most recent call last):\nKeyError: 'customer_id'",
}

st.set_page_config(page_title="Airflow AI Failure Analyzer", page_icon="✦", layout="wide")
st.markdown("""<style>.block-container{max-width:1180px;padding-top:2.5rem}.hero{padding:1.8rem 2rem;border-radius:18px;color:#f8fafc;background:linear-gradient(120deg,#0f172a,#0c4a6e);margin-bottom:1.5rem}.hero h1{margin:0;font-size:2.25rem}.hero p{color:#cbd5e1;margin-bottom:0}.card{border:1px solid #e2e8f0;background:#fff;border-radius:14px;padding:1.1rem 1.25rem;min-height:116px;box-shadow:0 2px 5px rgba(15,23,42,.04)}.eyebrow{color:#64748b;font-size:.78rem;letter-spacing:.08em;font-weight:700;text-transform:uppercase}.value{color:#0f172a;font-size:1.15rem;font-weight:700;margin-top:.35rem}</style>""", unsafe_allow_html=True)
st.markdown("""<div class="hero"><h1>Airflow AI Failure Analyzer</h1><p>Turn noisy task logs into a clear diagnosis, impact assessment, and next action.</p></div>""", unsafe_allow_html=True)
if "log_text" not in st.session_state:
    st.session_state.log_text = SAMPLES["Snowflake Authentication Error"]
st.markdown("#### Try a sample failure")
for column, (label, text) in zip(st.columns(5), SAMPLES.items()):
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
        except requests.RequestException as error:
            st.error(f"Could not reach the analysis API. Start the FastAPI backend first. ({error})")
if analysis := st.session_state.get("analysis"):
    st.markdown("### Analysis result")
    for column, label, value in zip(st.columns(2), ["Failure type", "Severity"], [analysis["failure_type"], analysis["severity"]]):
        column.markdown(f'<div class="card"><div class="eyebrow">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    for column, label, value in zip(st.columns(2), ["Root cause", "Summary"], [analysis["root_cause"], analysis["summary"]]):
        column.markdown(f'<div class="card"><div class="eyebrow">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)
    st.markdown("#### Recommended actions")
    for action in analysis["recommended_actions"]:
        st.markdown(f"- {action}")
