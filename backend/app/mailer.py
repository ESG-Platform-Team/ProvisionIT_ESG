"""
Outbound email. SMTP locally, Amazon SES in the deployment design.

Every message is written to data/mail as an .eml file whether or not it was
delivered, so there is always a record of what the platform sent and to whom.
When SMTP is not configured nothing leaves the machine; the message is saved and
the caller is told plainly that it was not delivered. That is the default, so a
demo can never email a real company by accident.

Configure with environment variables:

    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM, SMTP_STARTTLS (true), SMTP_SSL (false)
"""

from __future__ import annotations

import asyncio
import datetime
import os
import re
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

MAIL_DIR = Path(os.getenv("MAIL_DIR", "data/mail"))
MAX_RECIPIENTS = 10
_ADDRESS = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[A-Za-z]{2,}$")


def configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def sender() -> str:
    return os.getenv("SMTP_FROM", "Provision IT ESG Platform <esg-platform@localhost>")


def valid_address(address: str) -> bool:
    return bool(_ADDRESS.match(address.strip()))


def clean_recipients(addresses: list[str] | str) -> list[str]:
    """Split, trim, validate and de-duplicate. Raises ValueError with the first
    bad address rather than silently dropping it."""
    if isinstance(addresses, str):
        addresses = re.split(r"[,;\s]+", addresses)
    out: list[str] = []
    for a in addresses:
        a = a.strip()
        if not a:
            continue
        if not valid_address(a):
            raise ValueError(f"Not a valid email address: {a}")
        if a.lower() not in {x.lower() for x in out}:
            out.append(a)
    if not out:
        raise ValueError("At least one recipient is required")
    if len(out) > MAX_RECIPIENTS:
        raise ValueError(f"At most {MAX_RECIPIENTS} recipients per message")
    return out


def build(to: list[str], subject: str, text: str, html: str | None = None,
          attachments: list[tuple[str, bytes, str]] | None = None,
          reply_to: str | None = None, headers: dict | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="provisionit.esg")
    if reply_to:
        msg["Reply-To"] = reply_to
    for k, v in (headers or {}).items():
        msg[k] = v
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    for filename, data, mime in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream",
                           filename=filename)
    return msg


async def send(msg: EmailMessage, kind: str) -> dict:
    """Deliver if SMTP is configured, and always keep a copy. kind labels the
    record, for example 'report' or 'disclosure-request'."""
    delivered, error = False, None
    if configured():
        try:
            await asyncio.to_thread(_smtp_send, msg)
            delivered = True
        except (smtplib.SMTPException, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"

    MAIL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{kind}-{uuid.uuid4().hex[:8]}.eml"
    msg["X-Provision-Delivery"] = "smtp" if delivered else "not-sent"
    path = MAIL_DIR / name
    path.write_bytes(bytes(msg))

    return {
        "delivered": delivered,
        "mode": "smtp" if configured() else "outbox",
        "error": error,
        "record": str(path),
        "messageId": msg["Message-ID"],
        "to": msg["To"],
        "subject": msg["Subject"],
        "note": ("Delivered by SMTP" if delivered
                 else f"SMTP delivery failed, saved to {path}" if error
                 else f"SMTP is not configured, so nothing was sent. Saved to {path}"),
    }


def _smtp_send(msg: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    context = ssl.create_default_context()
    if os.getenv("SMTP_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as s:
            if user:
                s.login(user, password or "")
            s.send_message(msg)
        return
    with smtplib.SMTP(host, port, timeout=30) as s:
        if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            s.starttls(context=context)
        if user:
            s.login(user, password or "")
        s.send_message(msg)


def list_records(limit: int = 50) -> list[dict]:
    """What the platform has sent or saved, newest first. For the demo and for
    the audit trail."""
    if not MAIL_DIR.exists():
        return []
    from email import policy
    from email.parser import BytesParser

    out = []
    for path in sorted(MAIL_DIR.glob("*.eml"), reverse=True)[:limit]:
        try:
            msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        except Exception:  # noqa: BLE001
            continue
        out.append({
            "file": path.name, "to": msg["To"], "subject": msg["Subject"],
            "date": msg["Date"], "delivery": msg["X-Provision-Delivery"],
            "attachments": [p.get_filename() for p in msg.iter_attachments()],
        })
    return out
