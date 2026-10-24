"""
FastAPI service implementing api-contract v0.2.

v0.2 adds, without changing anything a v0.1 client relies on:
- pillars on POST /api/assessments, and a pillars array on the result
- the machine-interpretation statement on every result
- persisted runs and history
"""

from __future__ import annotations

import asyncio
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import companies, pillars, pipeline, store
from .matrix import FRAMEWORK_EDITION, MATRIX_VERSION

app = FastAPI(title="Provision IT ESG Assessment", version="0.2.0")

# The demo frontend is served from a plain http.server, on 8000 or 8001 when
# the browser has cached something else on 8000. Any localhost port is allowed
# for development; ALLOWED_ORIGINS adds anything else. Tighten both before the
# service leaves a laptop.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, pipeline.RunState] = {}
RESULTS: dict[str, dict] = {}


def _err(status: int, code: str, message: str):
    raise HTTPException(status, {"error": {"code": code, "message": message}})


# --- Accounts ----------------------------------------------------------------
# Sign-in arrives in feature/auth-sign-in. Until then every request runs as the
# guest below, and the routes already declare the dependency sign-in will use.

GUEST = {"userId": "usr_guest", "name": "Guest", "email": None}


async def require_user() -> dict:
    return GUEST


AUTH = [Depends(require_user)]


def _completed(run_id: str) -> dict:
    run = RESULTS.get(run_id) or store.get_run(run_id)
    if run is None:
        _err(404, "RUN_NOT_FOUND", "No completed run with that id")
    return run


# --- Health and search -------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "matrixVersion": MATRIX_VERSION,
        "frameworkEdition": FRAMEWORK_EDITION,
        "pillars": [{"pillar": k, "label": pillars.get(k)["label"],
                     "matrixVersion": pillars.get(k)["matrixVersion"],
                     "draft": pillars.get(k)["draft"]} for k in pillars.ORDER],
        "llmConfigured": bool(os.getenv("GEMINI_API_KEY")),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    }


@app.get("/api/companies", dependencies=AUTH)
async def search_companies(q: str = ""):
    return {"matches": companies.find(q)}


# --- Assessments -------------------------------------------------------------

class StartRun(BaseModel):
    asxCode: str
    pillar: str = "GOVERNANCE"          # contract v0.1
    pillars: list[str] | None = None    # contract v0.2, wins when present


async def _launch(company: dict, pillar_keys: list[str], user: dict | None = None) -> str:
    run_id = pipeline.new_run_id()
    state = pipeline.RunState(run_id, company, pillar_keys)
    RUNS[run_id] = state

    async def _work():
        try:
            payload = await pipeline.run_assessment(
                company, state, pillar_keys=pillar_keys)
            if user:
                payload["requestedBy"] = {"name": user["name"], "email": user.get("email")}
            RESULTS[run_id] = payload
            store.save_run(payload)
        except Exception as exc:  # noqa: BLE001
            state.status = "FAILED"
            state.error = str(exc)

    asyncio.create_task(_work())
    return run_id


@app.post("/api/assessments", status_code=202)
async def start_assessment(body: StartRun, user: dict = Depends(require_user)):
    company = companies.get(body.asxCode)
    if company is None:
        _err(404, "COMPANY_NOT_FOUND", f"No company {body.asxCode}")
    try:
        keys = pillars.normalise(body.pillars or body.pillar)
    except KeyError as exc:
        _err(400, "UNKNOWN_PILLAR", str(exc))
    run_id = await _launch(company, keys, user)
    return {"runId": run_id, "status": "QUEUED", "pillars": keys, "pollAfterMs": 1500}


@app.get("/api/assessments", dependencies=AUTH)
async def list_assessments(asxCode: str | None = None, limit: int = 50):
    return {"runs": store.list_runs(asxCode, min(max(limit, 1), 200))}


@app.get("/api/assessments/{run_id}", dependencies=AUTH)
async def get_assessment(run_id: str):
    if run_id in RESULTS:
        return RESULTS[run_id]
    state = RUNS.get(run_id)
    if state is None:
        stored = store.get_run(run_id)
        if stored:
            return stored
        _err(404, "RUN_NOT_FOUND", "No run with that id")
    if state.status == "FAILED":
        _err(500, "RUN_FAILED", state.error or "unknown")
    return {
        "runId": run_id,
        "status": state.status,
        "stage": state.stage,
        "pillars": state.pillars,
        "progress": round(state.progress, 3),
        "sourceLog": state.source_log,
        "runLog": state.log_lines[-12:],
    }


@app.get("/api/assessments/{run_id}/criteria/{code}/evidence", dependencies=AUTH)
async def get_evidence(run_id: str, code: str):
    result = _completed(run_id)
    docs = {d["sourceDocumentId"]: d for d in result["sourceLog"]}
    for p in result.get("pillars") or [{"principles": result["principles"]}]:
        for principle in p["principles"]:
            for row in principle["criteria"]:
                if row["criterionCode"].lower() != code.lower():
                    continue
                enriched = []
                for ev in row["evidence"]:
                    doc = docs.get(ev.get("sourceDocumentId"), {})
                    enriched.append({**ev, "sourceDocument": {
                        "sourceDocumentId": ev.get("sourceDocumentId"),
                        "title": doc.get("title"), "url": doc.get("url"),
                        "sourceGrade": doc.get("sourceGrade"),
                        "extractionMethod": doc.get("extractionMethod"),
                        "provenance": doc.get("provenance"),
                    }})
                return {"criterionCode": row["criterionCode"], "status": row["status"],
                        "interpretedBy": row.get("interpretedBy"), "evidence": enriched}
    _err(404, "CRITERION_NOT_FOUND", f"No criterion {code} in this run")


@app.get("/api/me/preferences")
async def preferences():
    return {"showSourceQuality": True, "showBothScores": True, "showPeerField": True}
