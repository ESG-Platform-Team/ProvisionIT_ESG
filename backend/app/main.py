"""
FastAPI service implementing api-contract v0.2.

v0.2 adds, without changing anything a v0.1 client relies on:
- pillars on POST /api/assessments, and a pillars array on the result
- the machine-interpretation statement on every result
- persisted runs and history
- the PDF report, and emailing it
- disclosure requests, and the company's response page at /respond/{token}
- accounts: every /api route except health and sign-in needs a signed-in user
"""

from __future__ import annotations

import asyncio
import os
import re

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from . import auth, companies, contacts, disclosure, mailer, pillars, pipeline, report, store
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


def public_base() -> str:
    """Where a company's browser can reach /respond. localhost in development,
    the public API domain once deployed."""
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")


def _err(status: int, code: str, message: str):
    raise HTTPException(status, {"error": {"code": code, "message": message}})


# --- Accounts ----------------------------------------------------------------

GUEST = {"userId": "usr_guest", "name": "Guest", "email": None}


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


async def require_user(authorization: str | None = Header(default=None)) -> dict:
    """Every /api route except health and sign-in depends on this. AUTH_REQUIRED=false
    turns it off for local scripts, never for a deployment."""
    if os.getenv("AUTH_REQUIRED", "true").lower() == "false":
        return GUEST
    user = auth.user_for_token(_bearer(authorization))
    if user is None:
        _err(401, "UNAUTHENTICATED", "Sign in to continue")
    return user


AUTH = [Depends(require_user)]


class SignUp(BaseModel):
    name: str
    email: str
    password: str


class SignIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup", status_code=201)
async def signup(body: SignUp):
    try:
        user = await asyncio.to_thread(auth.signup, body.name, body.email, body.password)
    except auth.AuthError as exc:
        _err(400, "SIGNUP_REJECTED", str(exc))
    return {"token": auth.issue_token(user), "tokenType": "Bearer",
            "expiresIn": auth.expire_minutes() * 60, "user": auth.public(user)}


@app.post("/api/auth/login")
async def login(body: SignIn):
    try:
        token, user = await asyncio.to_thread(auth.login, body.email, body.password)
    except auth.AuthError as exc:
        _err(401, "LOGIN_FAILED", str(exc))
    return {"token": token, "tokenType": "Bearer", "expiresIn": auth.expire_minutes() * 60,
            "user": auth.public(user)}


@app.post("/api/auth/logout")
async def logout(authorization: str | None = Header(default=None)):
    auth.logout(_bearer(authorization))
    return {"signedOut": True}


@app.get("/api/auth/me")
async def me(user: dict = Depends(require_user)):
    return {"user": auth.public(user) if user is not GUEST else GUEST}


def _completed(run_id: str) -> dict:
    run = RESULTS.get(run_id) or store.get_run(run_id)
    if run is None:
        _err(404, "RUN_NOT_FOUND", "No completed run with that id")
    return run


def _requests_for(asx_code: str) -> list[dict]:
    """Every request for a company, with due dates applied and saved back."""
    out = []
    for req in store.list_requests(asx_code):
        before = req["status"]
        disclosure.refresh(req)
        if req["status"] != before:
            store.save_request(req)
        out.append(req)
    return out


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
        "authRequired": os.getenv("AUTH_REQUIRED", "true").lower() != "false",
    }


@app.get("/api/companies", dependencies=AUTH)
async def search_companies(q: str = "", all: bool = False):
    """Search by name, code or website; all=true returns every company on file."""
    return {"matches": companies.all_companies() if all else companies.find(q)}


@app.get("/api/companies/{code}/contacts", dependencies=AUTH)
async def company_contacts(code: str):
    """Contact addresses the company publishes on its own website, ranked with
    shared role inboxes first. Nothing is guessed, stored or sent."""
    company = companies.get(code)
    if company is None:
        _err(404, "COMPANY_NOT_FOUND", f"No company {code}")
    if not company.get("website"):
        _err(400, "NO_WEBSITE", "This company has no website on file")
    found = await contacts.find(company["website"])
    found["company"] = {"asxCode": company["asxCode"], "name": company["name"]}
    return found


class NewCompany(BaseModel):
    name: str = ""
    website: str
    contactEmail: str = ""
    sector: str = ""
    asxCode: str = ""


@app.post("/api/companies", status_code=201)
async def add_company(body: NewCompany, user: dict = Depends(require_user)):
    """Add a private (unlisted) company so it can be assessed and sent requests.
    Adding a website that is already on file returns that company."""
    try:
        company = await asyncio.to_thread(companies.add_private, body.name, body.website,
                                          body.contactEmail, body.sector,
                                          user.get("userId") if user is not GUEST else None,
                                          body.asxCode)
    except companies.CompanyError as exc:
        _err(400, "COMPANY_REJECTED", str(exc))
    return company


# --- Assessments -------------------------------------------------------------

class StartRun(BaseModel):
    asxCode: str
    pillar: str = "GOVERNANCE"          # contract v0.1
    pillars: list[str] | None = None    # contract v0.2, wins when present


async def _launch(company: dict, pillar_keys: list[str], user: dict | None = None) -> str:
    run_id = pipeline.new_run_id()
    state = pipeline.RunState(run_id, company, pillar_keys)
    RUNS[run_id] = state
    requests = _requests_for(company["asxCode"])

    async def _work():
        try:
            payload = await pipeline.run_assessment(
                company, state, pillar_keys=pillar_keys,
                extra_documents=disclosure.response_documents(requests),
                disclosure_requests=[disclosure.summary(r) for r in requests],
            )
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
        + f"ESG disclosure assessment: {companies.label(c)}\n"
        f"Assessed {(run.get('completedAt') or '')[:10]}, run {run['runId']}\n\n"
        + "\n".join(lines)
        + "\n\nThe full report is attached as a PDF"
        + (", with the machine-readable result as JSON" if body.includeJson else "")
        + ".\n\nMachine interpretation\n" + run["interpretation"]["statement"] + "\n\n"
        + (f"Sent by {user['name']} ({user['email']}) via the Provision IT ESG platform\n"
           if user.get("email") else "Provision IT ESG platform\n")
    )
    msg = mailer.build(to, f"ESG assessment: {companies.label(c)}", text,
                       html=_report_email_html(run, body.message, body.includeJson, user),
                       attachments=attachments,
                       reply_to=os.getenv("SMTP_REPLY_TO") or user.get("email") or None)
    result = await mailer.send(msg, "report")
    store.log_email("report", result, user.get("userId"), run_id=run_id)
    return result


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
<div style="font-size:20px;font-weight:800;margin-bottom:4px">{e(companies.label(c))}</div>
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


# --- Disclosure requests -----------------------------------------------------

class NewRequest(BaseModel):
    contactEmail: str
    pillars: list[str] | None = None
    dueDays: int | None = None
    requestedBy: str | None = None


@app.post("/api/assessments/{run_id}/disclosure-requests", status_code=201)
async def create_request(run_id: str, body: NewRequest, user: dict = Depends(require_user)):
    run = _completed(run_id)
    existing = _requests_for(run["company"]["asxCode"])
    try:
        req = disclosure.create(run, body.contactEmail, body.pillars, body.dueDays,
                                body.requestedBy or user["name"], existing,
                                requested_by_email=user.get("email"))
    except (disclosure.RequestError, KeyError) as exc:
        _err(409 if "open" in str(exc) or "opted" in str(exc) or "asked not" in str(exc)
             else 400, "REQUEST_REJECTED", str(exc))
    req["requestedByEmail"] = user.get("email")
    await disclosure.send(req, public_base())
    store.save_request(req)
    store.log_email("disclosure-request", {
        "to": req["contactEmail"], "subject": "Information request " + req["requestId"],
        "delivered": req["delivery"]["delivered"], "record": req["delivery"]["record"]},
        user.get("userId"), run_id=run_id, request_id=req["requestId"])
    out = disclosure.public_view(req)
    out["responseUrl"] = disclosure.response_url(req, public_base())
    return out


class RequestForm(BaseModel):
    """The request form in the Requests tab: any company, chosen documents,
    written-in items, and optionally the gaps from its latest assessment."""
    companyCode: str
    contactEmail: str = ""
    contactName: str = ""
    documents: list[str] = Field(default_factory=list)
    custom: list[str] = Field(default_factory=list)
    message: str = Field(default="", max_length=2000)
    dueDays: int | None = None
    runId: str | None = None
    includeGaps: bool = False


def _form_request(body: RequestForm, user: dict, existing: list[dict] | None,
                  preview: bool = False) -> dict:
    company = companies.get(body.companyCode)
    if company is None:
        _err(404, "COMPANY_NOT_FOUND", f"No company {body.companyCode}")
    run = _completed(body.runId) if body.runId and body.includeGaps else None
    email = body.contactEmail.strip() or (company.get("contactEmail") or "")
    if preview and not mailer.valid_address(email):
        email = "contact@company.example"
    try:
        return disclosure.create(
            run, email, None, body.dueDays, user["name"], existing, company=company,
            documents=body.documents, custom=body.custom, include_gaps=body.includeGaps,
            contact_name=body.contactName, message=body.message,
            requested_by_email=user.get("email"))
    except disclosure.RequestError as exc:
        if preview:
            _err(400, "PREVIEW_INCOMPLETE", str(exc))
        _err(409 if "open" in str(exc) or "asked not" in str(exc) else 400,
             "REQUEST_REJECTED", str(exc))


@app.get("/api/disclosure-requests/catalogue", dependencies=AUTH)
async def request_catalogue():
    """The ESG documents the request form offers, grouped by pillar."""
    return {"documents": disclosure.catalogue(), "defaultDueDays": disclosure.DEFAULT_DUE_DAYS}


@app.post("/api/disclosure-requests/preview")
async def preview_request(body: RequestForm, user: dict = Depends(require_user)):
    """The exact email the form would send, without sending or saving it."""
    req = _form_request(body, user, None, preview=True)
    parts = disclosure.email_parts(req, public_base())
    return {"subject": parts["subject"], "text": parts["text"], "to": parts["to"],
            "itemCount": len(req["items"]), "dueAt": req["dueAt"]}


@app.post("/api/disclosure-requests", status_code=201)
async def send_request(body: RequestForm, user: dict = Depends(require_user)):
    existing = _requests_for(body.companyCode)
    req = _form_request(body, user, existing)
    await disclosure.send(req, public_base())
    store.save_request(req)
    store.log_email("disclosure-request", {
        "to": req["contactEmail"], "subject": "Information request " + req["requestId"],
        "delivered": req["delivery"]["delivered"], "record": req["delivery"]["record"]},
        user.get("userId"), run_id=req.get("runId"), request_id=req["requestId"])
    out = disclosure.public_view(req)
    out["responseUrl"] = disclosure.response_url(req, public_base())
    return out


@app.get("/api/disclosure-requests", dependencies=AUTH)
async def list_requests(asxCode: str | None = None):
    reqs = _requests_for(asxCode) if asxCode else [
        disclosure.refresh(r) for r in store.list_requests()]
    out = []
    for r in reqs:
        view = disclosure.public_view(r)
        if r["status"] == "SENT":
            view["responseUrl"] = disclosure.response_url(r, public_base())
        out.append(view)
    return {"requests": out}


def _request(request_id: str) -> dict:
    req = store.get_request(request_id)
    if req is None:
        _err(404, "REQUEST_NOT_FOUND", "No disclosure request with that id")
    before = req["status"]
    disclosure.refresh(req)
    if req["status"] != before:
        store.save_request(req)
    return req


@app.get("/api/disclosure-requests/{request_id}", dependencies=AUTH)
async def get_request(request_id: str):
    req = _request(request_id)
    view = disclosure.public_view(req)
    if req["status"] == "SENT":
        view["responseUrl"] = disclosure.response_url(req, public_base())
    return view


@app.get("/api/disclosure-requests/{request_id}/documents/{index}", dependencies=AUTH)
async def request_document(request_id: str, index: int, download: bool = False):
    """A document a company supplied in answer to a request."""
    from pathlib import Path

    req = _request(request_id)
    docs = (req.get("response") or {}).get("documents", [])
    if not 0 <= index < len(docs):
        _err(404, "DOCUMENT_NOT_FOUND", "No document with that number on this request")
    doc = docs[index]
    path = Path(doc["path"]).resolve()
    root = Path(disclosure.RESPONSE_DIR).resolve()
    if root not in path.parents or not path.exists():
        _err(404, "DOCUMENT_NOT_FOUND", "That document is no longer available")
    name = (doc.get("file") or path.name).replace('"', "")
    disposition = "attachment" if download else "inline"
    return Response(path.read_bytes(), media_type=doc["mediaType"], headers={
        "Content-Disposition": f'{disposition}; filename="{name}"'})


class CloseRequest(BaseModel):
    reason: str | None = None


@app.post("/api/disclosure-requests/{request_id}/close", dependencies=AUTH)
async def close_request(request_id: str, body: CloseRequest | None = None):
    req = _request(request_id)
    try:
        disclosure.close(req, body.reason if body else None)
    except disclosure.RequestError as exc:
        _err(409, "REQUEST_CLOSED", str(exc))
    store.save_request(req)
    return disclosure.public_view(req)


@app.post("/api/disclosure-requests/{request_id}/reassess", status_code=202)
async def reassess(request_id: str, user: dict = Depends(require_user)):
    """Run the same pillars again for the company. Documents from every answered
    request are included and marked as provided on request; unanswered requests
    annotate the criteria they covered."""
    req = _request(request_id)
    company = companies.get(req["company"]["asxCode"])
    if company is None:
        _err(404, "COMPANY_NOT_FOUND", "Company no longer in the registry")
    prior = _completed(req["runId"]) if req.get("runId") else None
    keys = (prior or {}).get("pillarsRequested") or req["pillars"] or list(pillars.ORDER)
    run_id = await _launch(company, keys, user)
    return {"runId": run_id, "status": "QUEUED", "pillars": keys, "pollAfterMs": 1500}


# --- The company's side: no login, the token is the credential -------------

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def _by_token(token: str) -> dict | None:
    if not _TOKEN.match(token):
        return None
    req = store.get_request_by_token(token)
    if req:
        before = req["status"]
        disclosure.refresh(req)
        if req["status"] != before:
            store.save_request(req)
    return req


@app.get("/respond/{token}", response_class=HTMLResponse)
async def response_page(token: str):
    req = _by_token(token)
    return HTMLResponse(disclosure.render_page(req), status_code=200 if req else 404)


@app.post("/respond/{token}", response_class=HTMLResponse)
async def submit_response(token: str, files: list[UploadFile] = File(default=[]),
                          note: str = Form(""), name: str = Form(""), email: str = Form("")):
    req = _by_token(token)
    if req is None:
        return HTMLResponse(disclosure.render_page(None), status_code=404)
    blobs = []
    for f in files[: disclosure.MAX_FILES + 1]:
        if not f.filename:
            continue
        data = await f.read(disclosure.MAX_FILE_BYTES + 1)
        blobs.append((f.filename, data))
    try:
        disclosure.record_response(req, blobs, note, name, email)
    except disclosure.RequestError as exc:
        return HTMLResponse(disclosure.render_page(req, error=str(exc)), status_code=400)
    store.save_request(req)
    n = len(req["response"]["documents"])
    return HTMLResponse(disclosure.render_page(
        req, message=f"Thank you. We received {n} item{'s' if n != 1 else ''}. They will be "
                     "recorded as provided on request in the next assessment."))


@app.post("/respond/{token}/decline", response_class=HTMLResponse)
async def decline_request(token: str, request: Request):
    req = _by_token(token)
    if req is None:
        return HTMLResponse(disclosure.render_page(None), status_code=404)
    form = await request.form()
    try:
        disclosure.decline(req, str(form.get("reason", "")), bool(form.get("optOut")),
                           str(form.get("name", "")))
    except disclosure.RequestError as exc:
        return HTMLResponse(disclosure.render_page(req, error=str(exc)), status_code=400)
    store.save_request(req)
    msg = "Thank you for letting us know. The request is closed."
    if req.get("optOut"):
        msg += " We will not send further requests to this company."
    return HTMLResponse(disclosure.render_page(req, message=msg))


@app.get("/api/me/preferences")
async def preferences():
    return {"showSourceQuality": True, "showBothScores": True, "showPeerField": True}
