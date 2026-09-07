"""
FastAPI service implementing api-contract-v0.1.

Endpoint shapes match the contract exactly, so the frontend switches from mock
to live by changing one environment variable.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import companies, pipeline
from .matrix import FRAMEWORK_EDITION, MATRIX_VERSION

app = FastAPI(title="Provision IT Governance Assessment", version="0.1.0")

# The demo frontend is served from a plain http.server on 8000, so it needs to
# be allowed through. Tighten this before anything leaves a laptop.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, pipeline.RunState] = {}
RESULTS: dict[str, dict] = {}


class StartRun(BaseModel):
    asxCode: str
    pillar: str = "GOVERNANCE"


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "matrixVersion": MATRIX_VERSION,
        "frameworkEdition": FRAMEWORK_EDITION,
        "llmConfigured": bool(os.getenv("GEMINI_API_KEY")),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }


@app.get("/api/companies")
async def search_companies(q: str = ""):
    return {"matches": companies.find(q)}


@app.post("/api/assessments", status_code=202)
async def start_assessment(body: StartRun):
    company = companies.get(body.asxCode)
    if company is None:
        raise HTTPException(404, {"error": {"code": "COMPANY_NOT_FOUND",
                                            "message": f"No company {body.asxCode}"}})

    run_id = pipeline.new_run_id()
    state = pipeline.RunState(run_id, company)
    RUNS[run_id] = state

    async def _work():
        try:
            RESULTS[run_id] = await pipeline.run_assessment(company, state)
        except Exception as exc:  # noqa: BLE001
            state.status = "FAILED"
            state.error = str(exc)

    asyncio.create_task(_work())
    return {"runId": run_id, "status": "QUEUED", "pollAfterMs": 1500}


@app.get("/api/assessments/{run_id}")
async def get_assessment(run_id: str):
    if run_id in RESULTS:
        return RESULTS[run_id]
    state = RUNS.get(run_id)
    if state is None:
        raise HTTPException(404, {"error": {"code": "RUN_NOT_FOUND",
                                            "message": "No run with that id"}})
    if state.status == "FAILED":
        raise HTTPException(500, {"error": {"code": "RUN_FAILED",
                                            "message": state.error or "unknown"}})
    return {
        "runId": run_id,
        "status": state.status,
        "stage": state.stage,
        "progress": round(state.progress, 3),
        "sourceLog": state.source_log,
        "runLog": state.log_lines[-12:],
    }


@app.get("/api/assessments/{run_id}/criteria/{code}/evidence")
async def get_evidence(run_id: str, code: str):
    result = RESULTS.get(run_id)
    if result is None:
        raise HTTPException(404, {"error": {"code": "RUN_NOT_FOUND",
                                            "message": "No completed run with that id"}})
    for principle in result["principles"]:
        for row in principle["criteria"]:
            if row["criterionCode"].lower() == code.lower():
                docs = {d["sourceDocumentId"]: d for d in result["sourceLog"]}
                enriched = []
                for ev in row["evidence"]:
                    doc = docs.get(ev.get("sourceDocumentId"), {})
                    enriched.append({**ev, "sourceDocument": {
                        "sourceDocumentId": ev.get("sourceDocumentId"),
                        "title": doc.get("title"),
                        "url": doc.get("url"),
                        "sourceGrade": doc.get("sourceGrade"),
                        "extractionMethod": doc.get("extractionMethod"),
                    }})
                return {"criterionCode": row["criterionCode"],
                        "status": row["status"], "evidence": enriched}
    raise HTTPException(404, {"error": {"code": "CRITERION_NOT_FOUND",
                                        "message": f"No criterion {code} in this run"}})


@app.get("/api/me/preferences")
async def preferences():
    return {"showSourceQuality": True, "showBothScores": True, "showPeerField": True}
