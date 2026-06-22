from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.analyzer import analyzer
from backend.schemas import AnalysisRequest, AnalysisResponse

app = FastAPI(title="Airflow AI Failure Analyzer API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8501"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/analyze", response_model=AnalysisResponse)
def analyze_failure(request: AnalysisRequest) -> AnalysisResponse:
    if not request.log_text.strip():
        raise HTTPException(status_code=422, detail="log_text cannot be blank")
    return analyzer.analyze(request.log_text)
