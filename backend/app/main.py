"""
FastAPI service implementing api-contract v0.2.

v0.2 adds, without changing anything a v0.1 client relies on:
- pillars on POST /api/assessments, and a pillars array on the result
- the machine-interpretation statement on every result
- persisted runs and history
- the PDF report, and emailing it
"""

from __future__ import annotations

import asyncio
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import companies, mailer, pillars, pipeline, report, store
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
        "smtpConfigured": mailer.configured(),
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


def _report_name(run: dict) -> str:
    date = (run.get("completedAt") or "")[:10]
    return f"{run['company']['asxCode']}-esg-assessment-{date}.pdf"


@app.get("/api/assessments/{run_id}/report.pdf", dependencies=AUTH)
async def report_pdf(run_id: str, download: bool = False):
    run = _completed(run_id)
    pdf = await asyncio.to_thread(report.render, run)
    disposition = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'{disposition}; filename="{_report_name(run)}"'})


class EmailReport(BaseModel):
    to: list[str] | str
    message: str | None = Field(default=None, max_length=2000)
    includeJson: bool = True


@app.post("/api/assessments/{run_id}/email")
async def email_report(run_id: str, body: EmailReport, user: dict = Depends(require_user)):
    run = _completed(run_id)
    try:
        to = mailer.clean_recipients(body.to)
    except ValueError as exc:
        _err(400, "BAD_RECIPIENT", str(exc))

    import json
    pdf = await asyncio.to_thread(report.render, run)
    attachments = [(_report_name(run), pdf, "application/pdf")]
    if body.includeJson:
        # Mick's second output: machine readable, for another platform.
        attachments.append((_report_name(run).replace(".pdf", ".json"),
                            json.dumps(run, indent=2).encode(), "application/json"))

    c = run["company"]
    lines = [f"  {p['label']:<14} {p['result']['band'].replace('_', ' ').title():<22} "
             f"confidence {p['result']['confidence']}" for p in run.get("pillars", [])]
    text = (
        (body.message.strip() + "\n\n" if body.message else "")
        + f"ESG disclosure assessment: {c['name']} (ASX: {c['asxCode']})\n"
        f"Assessed {(run.get('completedAt') or '')[:10]}, run {run['runId']}\n\n"
        + "\n".join(lines)
        + "\n\nThe full report is attached as a PDF"
        + (", with the machine-readable result as JSON" if body.includeJson else "")
        + ".\n\nMachine interpretation\n" + run["interpretation"]["statement"] + "\n\n"
        + (f"Sent by {user['name']} ({user['email']}) via the Provision IT ESG platform\n"
           if user.get("email") else "Provision IT ESG platform\n")
    )
    msg = mailer.build(to, f"ESG assessment: {c['name']} ({c['asxCode']})", text,
                       html=_report_email_html(run, body.message, body.includeJson, user),
                       attachments=attachments,
                       reply_to=os.getenv("SMTP_REPLY_TO") or user.get("email") or None)
    return await mailer.send(msg, "report")


def _report_email_html(run: dict, message: str | None, include_json: bool,
                       user: dict | None = None) -> str:
    """The same content as the plain text email, laid out so the summary reads
    as a table in mail clients that show HTML. Plain text stays the fallback."""
    from html import escape as e

    c = run["company"]
    rows = "".join(
        f'<tr><td style="padding:10px 14px;border-bottom:1px solid #E7E8EC">{e(p["label"])}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #E7E8EC;font-weight:700">'
        f'{e(p["result"]["band"].replace("_", " ").title())}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #E7E8EC;text-align:center">'
        f'{e(str(p["result"]["confidence"]))}</td></tr>'
        for p in run.get("pillars", []))
    note = (f'<p style="margin:0 0 18px;line-height:1.6">{e(message.strip())}</p>'
            if message and message.strip() else "")
    sender = (f"Sent by {e(user['name'])} ({e(user['email'])}) via the "
              if user and user.get("email") else "")
    attached = "the full report as a PDF" + (", and the machine-readable result as JSON"
                                              if include_json else "")
    return f"""<!doctype html><html><body style="margin:0;background:#F4F5F7;
font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#0E0F14">
<div style="max-width:620px;margin:0 auto;background:#fff">
<div style="background:#0E0F14;border-top:4px solid #F4BF3F;padding:18px 24px;color:#F4F5F7;
font-weight:700;letter-spacing:.02em">Provision IT &middot; ESG assessment</div>
<div style="padding:24px">
{note}
<div style="font-size:20px;font-weight:800;margin-bottom:4px">{e(c['name'])} (ASX: {e(c['asxCode'])})</div>
<div style="font-size:13px;color:#5A5F6D;margin-bottom:18px">Assessed
{e((run.get('completedAt') or '')[:10])} &middot; run {e(run['runId'])}</div>
<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:18px">
<tr style="background:#F4F5F7;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#5A5F6D">
<th style="padding:8px 14px;text-align:left">Pillar</th><th style="padding:8px 14px;text-align:left">Band</th>
<th style="padding:8px 14px">Confidence</th></tr>{rows}</table>
<p style="margin:0 0 18px;line-height:1.6">Attached: {attached}.</p>
<div style="background:#FDF3D8;border-left:3px solid #F4BF3F;padding:12px 16px;font-size:13px;
line-height:1.6"><b>Machine interpretation.</b> {e(run['interpretation']['statement'])}</div>
</div>
<div style="padding:14px 24px;font-size:12px;color:#8A8F9C;border-top:1px solid #E7E8EC">
{sender}Provision IT ESG platform</div></div></body></html>"""


@app.get("/api/outbox", dependencies=AUTH)
async def outbox(limit: int = 50):
    return {"smtpConfigured": mailer.configured(), "messages": mailer.list_records(limit)}


@app.get("/api/me/preferences")
async def preferences():
    return {"showSourceQuality": True, "showBothScores": True, "showPeerField": True}
