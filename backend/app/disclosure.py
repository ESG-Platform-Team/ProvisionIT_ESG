"""
Disclosure requests: asking a company directly for what public sources lacked.

This does not scrape anything private. It sends the company a list of the
criteria we could not answer from public documents and a link where it can
upload what it is willing to share. The rules:

1. A person starts every request. The platform never emails a company on its
   own initiative, and it will not open a second request while one is open.
2. The email says who is asking, why, how anything supplied will be used, what
   happens if there is no answer, and how to opt out. An opt-out is honoured.
3. Anything supplied is recorded as provided on request and graded below a
   published document, because it has not been open to public scrutiny.
4. No answer by the due date is recorded, and the criteria it covered stay as
   they were: a gap stays insufficient information, a public silence stays not
   disclosed. Silence in reply to a request is never scored as a zero.

Status runs SENT, then one of RESPONDED, DECLINED or NO_RESPONSE.
"""

from __future__ import annotations

import datetime
import html
import os
import re
import secrets
import uuid
from pathlib import Path

from . import companies, mailer, pillars

DEFAULT_DUE_DAYS = int(os.getenv("DISCLOSURE_DUE_DAYS", "21"))
RESPONSE_DIR = Path(os.getenv("RESPONSE_DIR", "data/responses"))
ALLOWED_TYPES = {".pdf": "application/pdf", ".html": "text/html", ".htm": "text/html",
                 ".txt": "text/plain"}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 10
REQUESTABLE = ("EVIDENCE_GAP", "NOT_DISCLOSED")


class RequestError(ValueError):
    pass


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(ts: str | None) -> datetime.datetime | None:
    if not ts:
        return None
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def requestable_items(run: dict, pillar_keys: list[str] | None = None) -> list[dict]:
    """Criteria the public sources did not answer, across the chosen pillars."""
    wanted = set(pillars.normalise(pillar_keys)) if pillar_keys else None
    items = []
    for p in run.get("pillars", []):
        if wanted and p["pillar"] not in wanted:
            continue
        for principle in p["principles"]:
            for row in principle["criteria"]:
                if row["status"] in REQUESTABLE:
                    items.append({"criterionCode": row["criterionCode"], "pillar": p["pillar"],
                                  "pillarLabel": p["label"], "question": row["question"],
                                  "status": row["status"]})
    return items


def create(run: dict, contact_email: str, pillar_keys: list[str] | None = None,
           due_days: int | None = None, requested_by: str | None = None,
           existing: list[dict] | None = None) -> dict:
    """Build a request from a completed run. Raises RequestError when there is
    nothing to ask for, the address is invalid, the company has opted out, or a
    request is already open."""
    if not mailer.valid_address(contact_email or ""):
        raise RequestError("A valid company contact email is required")
    existing = [refresh(r) for r in (existing or [])]
    if any(r.get("optOut") for r in existing):
        raise RequestError("This company has asked not to receive further requests")
    open_ = [r for r in existing if r["status"] == "SENT"]
    if open_:
        raise RequestError(f"Request {open_[0]['requestId']} is still open for this company")

    items = requestable_items(run, pillar_keys)
    if not items:
        raise RequestError("Every criterion in scope was answered from public sources; "
                           "there is nothing to request")

    due = max(3, min(60, due_days or DEFAULT_DUE_DAYS))
    created = _now()
    company = run["company"]
    return {
        "requestId": f"req_{uuid.uuid4().hex[:16]}",
        "token": secrets.token_urlsafe(24),
        "company": {"asxCode": company["asxCode"], "name": company["name"],
                    "listed": company.get("listed", True)},
        "runId": run["runId"],
        "contactEmail": contact_email.strip(),
        "requestedBy": (requested_by or "").strip()[:80] or None,
        "pillars": sorted({i["pillar"] for i in items}, key=pillars.ORDER.index),
        "items": items,
        "criteria": [i["criterionCode"] for i in items],
        "status": "SENT",
        "createdAt": _iso(created),
        "sentAt": _iso(created),
        "dueAt": _iso(created + datetime.timedelta(days=due)),
        "respondedAt": None,
        "closedAt": None,
        "delivery": None,
        "response": None,
        "optOut": False,
    }


def _labels(keys: list[str]) -> str:
    names = [pillars.get(k)["label"].lower() for k in keys]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def response_url(req: dict, public_base: str) -> str:
    return f"{public_base.rstrip('/')}/respond/{req['token']}"


def compose(req: dict, public_base: str):
    company = req["company"]
    due = req["dueAt"][:10]
    link = response_url(req, public_base)
    labels = _labels(req["pillars"])
    lines = "\n".join(f"  {i['criterionCode']:<6} {i['question']}" for i in req["items"])
    on_behalf = f" on behalf of {req['requestedBy']}" if req.get("requestedBy") else ""
    text = f"""Dear {company['name']} team,

Provision IT is preparing an assessment of the {labels} disclosures of
{companies.label(company)} using publicly available information.
For the items below we could not find a published disclosure, or could not
retrieve the document that would contain one.

If you are able to help, please share any relevant document, or tell us where it
is published, by {due}:

{lines}

Respond securely, or decline, at:
{link}

How your response is used
- Anything you provide is recorded as "provided on request", graded separately
  from published documents, and used only for this assessment.
- If we have not heard from you by {due}, these items are reported as
  insufficient information. That describes the information available to us; it
  is not a finding against the company.
- You are welcome to reply to this email with any questions.

If you would prefer not to receive requests like this, choose "decline" at the
link above and tick "no further requests", and we will not contact you again.

Provision IT Pty Ltd, Melbourne
Sent by the Provision IT ESG platform{on_behalf}. Reference {req['requestId']}.
"""
    subject = (f"Information request: {labels} disclosures, "
               f"{companies.label(company)}")
    return mailer.build(
        [req["contactEmail"]], subject, text,
        reply_to=os.getenv("SMTP_REPLY_TO") or req.get("requestedByEmail") or None,
        headers={"X-Provision-Request": req["requestId"]},
    )


async def send(req: dict, public_base: str) -> dict:
    result = await mailer.send(compose(req, public_base), "disclosure-request")
    req["delivery"] = {k: result[k] for k in ("delivered", "mode", "error", "note", "record")}
    return req


def refresh(req: dict) -> dict:
    """Apply the due date. Only a request that was actually delivered can lapse
    into NO_RESPONSE; one that was saved but never emailed stays open, because a
    company cannot fail to answer an email it never received."""
    if req["status"] == "SENT" and (req.get("delivery") or {}).get("delivered"):
        due = _parse(req.get("dueAt"))
        if due and _now() > due:
            req["status"] = "NO_RESPONSE"
            req["closedAt"] = req["dueAt"]
            req["closedReason"] = "Due date passed without a response"
    return req


def close(req: dict, reason: str | None = None) -> dict:
    """An analyst closes an open request early. Recorded as NO_RESPONSE."""
    if req["status"] != "SENT":
        raise RequestError(f"Request is already {req['status']}")
    req["status"] = "NO_RESPONSE"
    req["closedAt"] = _iso(_now())
    req["closedReason"] = (reason or "Closed by analyst without a response")[:200]
    return req


def _safe_name(name: str) -> str:
    name = Path(name or "document").name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip() or "document"
    return name[:120]


def record_response(req: dict, files: list[tuple[str, bytes]], note: str = "",
                    name: str = "", email: str = "") -> dict:
    if req["status"] != "SENT":
        raise RequestError("This request is no longer open")
    if not files and not note.strip():
        raise RequestError("Attach at least one document or write a note")
    if len(files) > MAX_FILES:
        raise RequestError(f"At most {MAX_FILES} files")

    folder = RESPONSE_DIR / req["requestId"]
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for filename, data in files:
        safe = _safe_name(filename)
        ext = Path(safe).suffix.lower()
        if ext not in ALLOWED_TYPES:
            raise RequestError(f"{safe}: only PDF, HTML or plain text files are accepted")
        if len(data) > MAX_FILE_BYTES:
            raise RequestError(f"{safe}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
        if not data:
            continue
        path = folder / safe
        path.write_bytes(data)
        saved.append({"title": f"{Path(safe).stem} (provided on request)", "file": safe,
                      "path": str(path), "mediaType": ALLOWED_TYPES[ext],
                      "bytes": len(data)})
    if note.strip():
        path = folder / "response-note.txt"
        path.write_text(note.strip()[:20000])
        saved.append({"title": "Response note (provided on request)", "file": path.name,
                      "path": str(path), "mediaType": "text/plain",
                      "bytes": path.stat().st_size})

    req["status"] = "RESPONDED"
    req["respondedAt"] = _iso(_now())
    req["response"] = {"documents": saved, "respondentName": name.strip()[:120] or None,
                       "respondentEmail": email.strip()[:200] or None}
    return req


def decline(req: dict, reason: str = "", opt_out: bool = False, name: str = "") -> dict:
    if req["status"] != "SENT":
        raise RequestError("This request is no longer open")
    req["status"] = "DECLINED"
    req["respondedAt"] = _iso(_now())
    req["optOut"] = bool(opt_out)
    req["response"] = {"declineReason": reason.strip()[:2000] or None,
                       "respondentName": name.strip()[:120] or None, "documents": []}
    return req


def response_documents(requests: list[dict]) -> list[dict]:
    """Documents from every answered request, ready for the pipeline."""
    out = []
    for r in requests:
        if r["status"] == "RESPONDED":
            for d in (r.get("response") or {}).get("documents", []):
                out.append({"title": d["title"], "path": d["path"],
                            "mediaType": d["mediaType"], "requestId": r["requestId"]})
    return out


def summary(req: dict) -> dict:
    """What travels inside a run payload. No token: the token is the company's
    key to the response page and must not appear in a report or an export."""
    delivered = (req.get("delivery") or {}).get("delivered")
    return {
        "requestId": req["requestId"], "status": req["status"],
        "delivered": bool(delivered),
        "contactEmail": req["contactEmail"], "criteria": req["criteria"],
        "pillars": req["pillars"], "sentAt": req["sentAt"], "dueAt": req["dueAt"],
        "respondedAt": req.get("respondedAt"), "closedAt": req.get("closedAt"),
        "documentsProvided": len((req.get("response") or {}).get("documents", [])),
    }


def public_view(req: dict) -> dict:
    """The analyst's view over the API. Includes the response link so it can be
    opened in a demo, but never the raw token on its own."""
    out = summary(req)
    out.update({"company": req["company"], "runId": req.get("runId"),
                "items": req["items"], "requestedBy": req.get("requestedBy"),
                "delivery": req.get("delivery"), "response": req.get("response"),
                "optOut": req.get("optOut", False),
                "closedReason": req.get("closedReason")})
    return out


# --- The company's response page --------------------------------------------

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Information request · Provision IT</title>
<style>
body{{margin:0;background:#F4F5F7;color:#0E0F14;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}}
.top{{background:#0E0F14;color:#F4F5F7;padding:22px 24px;border-top:4px solid #F4BF3F}}
.wrap{{max-width:760px;margin:0 auto}}
.mark{{display:inline-flex;align-items:center;gap:12px;font-weight:700;letter-spacing:.01em}}
.mark span{{background:#F4BF3F;color:#fff;width:34px;height:38px;display:inline-flex;align-items:flex-start;justify-content:center;font-size:28px;font-weight:800;border-radius:8px}}
main{{padding:28px 24px 64px}}
h1{{font-size:26px;line-height:1.15;text-transform:uppercase;margin:6px 0 10px}}
.k{{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8A6A12}}
p{{line-height:1.65;color:#4A4E5C}}
ol{{background:#fff;border:1px solid #DCDEE4;padding:16px 20px 16px 40px}}
li{{margin:6px 0;line-height:1.55}} code{{font-size:12px;color:#8A8F9C}}
form{{background:#fff;border:1px solid #DCDEE4;padding:20px;margin-top:18px}}
label{{display:block;font-size:13px;margin:12px 0 6px;color:#0E0F14}}
input[type=text],input[type=email],textarea{{width:100%;box-sizing:border-box;border:1px solid #C6CAD4;padding:10px;font:inherit}}
textarea{{min-height:90px}}
button{{margin-top:16px;background:#F4BF3F;border:none;padding:12px 22px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}}
button.ghost{{background:transparent;border:1px solid #0E0F14}}
.note{{border-left:3px solid #F4BF3F;background:#FDF3D8;padding:12px 16px;margin:16px 0;color:#0E0F14}}
.err{{border-left:3px solid #B3261E;background:#FCE8E6;padding:12px 16px;margin:16px 0}}
</style></head><body>
<div class="top"><div class="wrap"><div class="mark"><span>*</span>Provision IT</div></div></div>
<main><div class="wrap">{body}</div></main></body></html>"""


def render_page(req: dict | None, message: str | None = None, error: str | None = None) -> str:
    e = html.escape
    if req is None:
        body = ('<div class="k">Information request</div><h1>Link not recognised</h1>'
                '<p>This link is not valid. If you received a request from Provision IT, '
                'reply to that email and we will resend it.</p>')
        return _PAGE.format(body=body)

    company = req["company"]
    head = (f'<div class="k">Information request · {e(req["requestId"])}</div>'
            f'<h1>{e(company["name"])}</h1>')
    if message:
        return _PAGE.format(body=head + f'<div class="note">{e(message)}</div>')

    if req["status"] != "SENT":
        state = {"RESPONDED": "has been answered", "DECLINED": "was declined",
                 "NO_RESPONSE": "has closed"}.get(req["status"], "is closed")
        return _PAGE.format(body=head + f'<p>This request {state}. Thank you.</p>')

    items = "".join(f'<li><code>{e(i["criterionCode"])}</code> {e(i["question"])}</li>'
                    for i in req["items"])
    err = f'<div class="err">{e(error)}</div>' if error else ""
    body = f"""{head}{err}
<p>Provision IT is assessing the published {e(_labels(req["pillars"]))}
disclosures of {e(company["name"])}. We could not find a published disclosure for the items
below. If you can help, please attach any relevant document or tell us where it is published,
by <strong>{e(req["dueAt"][:10])}</strong>.</p>
<ol>{items}</ol>
<div class="note">Anything you provide is recorded as <em>provided on request</em>, graded separately
from published documents, and used only for this assessment. If there is no response by the due
date, these items are reported as insufficient information, which is not a finding against the company.</div>
<form method="post" enctype="multipart/form-data" action="">
  <label>Documents (PDF, HTML or text, up to {MAX_FILES} files, {MAX_FILE_BYTES // (1024 * 1024)} MB each)</label>
  <input type="file" name="files" multiple accept=".pdf,.html,.htm,.txt">
  <label>Note, or where the information is published</label>
  <textarea name="note" placeholder="For example: our modern slavery statement is on the Australian Register at …"></textarea>
  <label>Your name</label><input type="text" name="name">
  <label>Your email</label><input type="email" name="email">
  <button type="submit">Send response</button>
</form>
<form method="post" action="/respond/{e(req["token"])}/decline">
  <label>Prefer not to respond? Tell us why (optional)</label>
  <textarea name="reason"></textarea>
  <label><input type="checkbox" name="optOut" value="1"> No further requests to this company</label>
  <label>Your name</label><input type="text" name="name">
  <button type="submit" class="ghost">Decline this request</button>
</form>"""
    return _PAGE.format(body=body)
