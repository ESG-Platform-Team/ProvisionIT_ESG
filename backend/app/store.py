"""
Persistence, on the relational schema in db.py.

The rest of the backend talks to this module with plain dicts in the API's own
shape; this module maps them to rows. Swapping SQLite for PostgreSQL is a
DATABASE_URL change, not a code change.
"""

from __future__ import annotations

import datetime

from sqlalchemy import delete, select

from . import db

# --- helpers -------------------------------------------------------------------


def _dt(value) -> datetime.datetime | None:
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _iso(value: datetime.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _company_row(s, company: dict) -> db.Company:
    """Find the company by code, creating it from the dict if this is the first
    time it is seen (for example a listed company from the seed registry)."""
    code = (company.get("asxCode") or company.get("code") or "").upper()
    row = s.scalar(select(db.Company).where(db.Company.code == code))
    if row is None:
        row = db.Company(code=code, name=company.get("name") or code,
                         website=company.get("website") or "",
                         sector=company.get("sector"), tier=company.get("tier"),
                         listed=company.get("listed", True),
                         contact_email=company.get("contactEmail"))
        s.add(row)
        s.flush()
    return row


# --- users and tokens ------------------------------------------------------------


def _user_dict(u: db.User) -> dict:
    return {"userId": u.id, "name": u.name, "email": u.email, "role": u.role,
            "passwordHash": u.password_hash, "createdAt": _iso(u.created_at),
            "lastLoginAt": _iso(u.last_login_at)}


def save_user(user: dict) -> None:
    with db.session() as s, s.begin():
        row = s.get(db.User, user["userId"]) or db.User(id=user["userId"])
        row.name, row.email = user["name"], user["email"].lower()
        row.password_hash = user["passwordHash"]
        row.role = user.get("role", "analyst")
        row.created_at = _dt(user.get("createdAt")) or db.utcnow()
        s.add(row)


def get_user(user_id: str) -> dict | None:
    with db.session() as s:
        u = s.get(db.User, user_id)
        return _user_dict(u) if u else None


def get_user_by_email(email: str) -> dict | None:
    with db.session() as s:
        u = s.scalar(select(db.User).where(db.User.email == email.lower()))
        return _user_dict(u) if u else None


def touch_login(user_id: str) -> None:
    with db.session() as s, s.begin():
        u = s.get(db.User, user_id)
        if u:
            u.last_login_at = db.utcnow()


def revoke_token(jti: str, user_id: str, expires_at: datetime.datetime) -> None:
    with db.session() as s, s.begin():
        if s.get(db.RevokedToken, jti) is None:
            s.add(db.RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
        # Housekeeping: a revoked token past its expiry can never be used anyway.
        s.execute(delete(db.RevokedToken).where(db.RevokedToken.expires_at < db.utcnow()))


def is_revoked(jti: str) -> bool:
    with db.session() as s:
        return s.get(db.RevokedToken, jti) is not None


# --- companies -------------------------------------------------------------------


def _company_dict(c: db.Company) -> dict:
    return {"asxCode": c.code, "name": c.name, "website": c.website, "sector": c.sector,
            "tier": c.tier, "listed": c.listed, "contactEmail": c.contact_email,
            "extraUrls": [], "createdAt": _iso(c.created_at)}


def save_company(company: dict, created_by: str | None = None) -> dict:
    with db.session() as s, s.begin():
        row = _company_row(s, company)
        row.name = company.get("name") or row.name
        row.website = company.get("website") or row.website
        row.sector, row.tier = company.get("sector", row.sector), company.get("tier", row.tier)
        row.listed = company.get("listed", row.listed)
        row.contact_email = company.get("contactEmail", row.contact_email)
        if created_by and not row.created_by:
            row.created_by = created_by
        s.flush()
        return _company_dict(row)


def get_company(code: str) -> dict | None:
    with db.session() as s:
        c = s.scalar(select(db.Company).where(db.Company.code == code.upper()))
        return _company_dict(c) if c else None


def list_companies(listed: bool | None = None) -> list[dict]:
    with db.session() as s:
        q = select(db.Company).order_by(db.Company.name)
        if listed is not None:
            q = q.where(db.Company.listed == listed)
        return [_company_dict(c) for c in s.scalars(q)]


# --- assessment runs -------------------------------------------------------------


def save_run(payload: dict) -> None:
    with db.session() as s, s.begin():
        company = _company_row(s, payload["company"])
        user = None
        email = (payload.get("requestedBy") or {}).get("email")
        if email:
            user = s.scalar(select(db.User).where(db.User.email == email.lower()))
        run = s.get(db.AssessmentRun, payload["runId"]) or db.AssessmentRun(id=payload["runId"])
        interp = payload.get("interpretation") or {}
        run.company_id = company.id
        run.requested_by = user.id if user else None
        run.status = payload.get("status", "COMPLETE")
        run.pillars = ",".join(payload.get("pillarsRequested", []))
        run.engine, run.model = interp.get("engine"), interp.get("model")
        run.requested_at = _dt(payload.get("requestedAt"))
        run.completed_at = _dt(payload.get("completedAt"))
        run.payload = payload
        if run in s:
            # Replace child rows: delete first so unique keys do not collide.
            s.execute(delete(db.PillarResult).where(db.PillarResult.run_id == run.id))
            s.execute(delete(db.SourceDocument).where(db.SourceDocument.run_id == run.id))
            s.flush()
            s.expire(run, ["pillar_results", "source_documents"])
        run.pillar_results = [
            db.PillarResult(pillar=p["pillar"], matrix_version=p["matrixVersion"],
                            band=p["result"]["band"], confidence=p["result"].get("confidence"),
                            transparency=(p["result"].get("transparencyScore") or {}).get("value"),
                            practice=(p["result"].get("practiceScore") or {}).get("value"))
            for p in payload.get("pillars", [])]
        run.source_documents = [
            db.SourceDocument(title=(d.get("title") or "")[:300], url=d.get("url"),
                              source_type=d.get("sourceType"), outcome=d.get("outcome", ""),
                              grade=d.get("sourceGrade"),
                              provenance=d.get("provenance") or "PUBLIC")
            for d in payload.get("sourceLog", [])]
        s.add(run)


def get_run(run_id: str) -> dict | None:
    with db.session() as s:
        run = s.get(db.AssessmentRun, run_id)
        return run.payload if run else None


def list_runs(asx_code: str | None = None, limit: int = 50) -> list[dict]:
    """Summaries for the history screen, newest first, from the relational
    columns rather than by unpacking every payload."""
    with db.session() as s:
        q = (select(db.AssessmentRun).join(db.Company)
             .order_by(db.AssessmentRun.completed_at.desc()).limit(limit))
        if asx_code:
            q = q.where(db.Company.code == asx_code.upper())
        out = []
        for run in s.scalars(q):
            user = s.get(db.User, run.requested_by) if run.requested_by else None
            order = {k: i for i, k in enumerate(run.pillars.split(","))}
            out.append({
                "runId": run.id,
                "company": {"asxCode": run.company.code, "name": run.company.name},
                "completedAt": _iso(run.completed_at),
                "requestedBy": user.name if user else None,
                "pillars": [{"pillar": p.pillar, "band": p.band, "confidence": p.confidence,
                             "matrixVersion": p.matrix_version}
                            for p in sorted(run.pillar_results,
                                            key=lambda p: order.get(p.pillar, 9))],
            })
        return out


# --- disclosure requests ---------------------------------------------------------


def save_request(req: dict) -> None:
    with db.session() as s, s.begin():
        company = _company_row(s, req["company"])
        row = s.get(db.DisclosureRequest, req["requestId"]) or db.DisclosureRequest(
            id=req["requestId"])
        user = None
        if req.get("requestedByEmail"):
            user = s.scalar(select(db.User).where(
                db.User.email == req["requestedByEmail"].lower()))
        row.token = req["token"]
        row.company_id = company.id
        row.run_id = req.get("runId") if req.get("runId") and s.get(
            db.AssessmentRun, req["runId"]) else None
        row.requested_by = user.id if user else row.requested_by
        row.contact_email = req["contactEmail"]
        row.status = req["status"]
        row.delivered = bool((req.get("delivery") or {}).get("delivered"))
        row.opt_out = bool(req.get("optOut"))
        row.created_at = _dt(req["createdAt"])
        row.due_at = _dt(req.get("dueAt"))
        row.responded_at = _dt(req.get("respondedAt"))
        row.closed_at = _dt(req.get("closedAt"))
        row.detail = req
        if row in s:
            s.execute(delete(db.RequestItem).where(db.RequestItem.request_id == row.id))
            s.execute(delete(db.RequestDocument).where(db.RequestDocument.request_id == row.id))
            s.flush()
            s.expire(row, ["items", "documents"])
        row.items = [db.RequestItem(criterion_code=i["criterionCode"], pillar=i["pillar"],
                                    status_at_request=i["status"]) for i in req["items"]]
        row.documents = [db.RequestDocument(title=d["title"][:300], path=d["path"],
                                            media_type=d["mediaType"], bytes=d["bytes"])
                         for d in (req.get("response") or {}).get("documents", [])]
        s.add(row)


def get_request(request_id: str) -> dict | None:
    with db.session() as s:
        row = s.get(db.DisclosureRequest, request_id)
        return dict(row.detail) if row else None


def get_request_by_token(token: str) -> dict | None:
    with db.session() as s:
        row = s.scalar(select(db.DisclosureRequest).where(db.DisclosureRequest.token == token))
        return dict(row.detail) if row else None


def list_requests(asx_code: str | None = None) -> list[dict]:
    with db.session() as s:
        q = (select(db.DisclosureRequest).join(db.Company)
             .order_by(db.DisclosureRequest.created_at.desc()))
        if asx_code:
            q = q.where(db.Company.code == asx_code.upper())
        return [dict(r.detail) for r in s.scalars(q)]


# --- email log -------------------------------------------------------------------


def log_email(kind: str, result: dict, sent_by: str | None = None,
              run_id: str | None = None, request_id: str | None = None) -> None:
    with db.session() as s, s.begin():
        s.add(db.EmailLog(kind=kind, recipients=result.get("to") or "",
                          subject=(result.get("subject") or "")[:300],
                          delivered=bool(result.get("delivered")),
                          record_path=result.get("record"),
                          sent_by=sent_by if sent_by and s.get(db.User, sent_by) else None,
                          run_id=run_id, request_id=request_id))


def email_log(limit: int = 50) -> list[dict]:
    with db.session() as s:
        rows = s.scalars(select(db.EmailLog).order_by(db.EmailLog.id.desc()).limit(limit))
        return [{"kind": r.kind, "to": r.recipients, "subject": r.subject,
                 "delivered": r.delivered, "sentBy": r.sent_by,
                 "createdAt": _iso(r.created_at)} for r in rows]
