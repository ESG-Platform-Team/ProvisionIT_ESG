"""
Persistence. SQLite locally, RDS PostgreSQL in the deployment design.

Two things have to survive a restart. Completed runs, so history and exported
reports stay reproducible. And disclosure requests, because a company answers
days after the request is sent, long after the process that sent it has gone.
And accounts and sessions, so people stay signed in across a restart.

Payloads are stored as JSON rather than normalised into the domain tables. The
contract shape is the thing that is stable; the relational schema on the class
diagram is where this goes when it moves to RDS.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "data/platform.db"))
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    asx_code     TEXT NOT NULL,
    pillars      TEXT NOT NULL,
    completed_at TEXT,
    payload      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_by_company ON runs (asx_code, completed_at);

CREATE TABLE IF NOT EXISTS disclosure_requests (
    request_id   TEXT PRIMARY KEY,
    token        TEXT NOT NULL UNIQUE,
    asx_code     TEXT NOT NULL,
    run_id       TEXT,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    due_at       TEXT,
    payload      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS requests_by_company ON disclosure_requests (asx_code, created_at);

CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    email        TEXT NOT NULL UNIQUE,
    payload      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_run(payload: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, asx_code, pillars, completed_at, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (payload["runId"], payload["company"]["asxCode"],
             ",".join(payload.get("pillarsRequested", [])),
             payload.get("completedAt"), json.dumps(payload)),
        )


def get_run(run_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_runs(asx_code: str | None = None, limit: int = 50) -> list[dict]:
    """Summaries for the history screen, newest first."""
    sql = "SELECT payload FROM runs"
    args: tuple = ()
    if asx_code:
        sql += " WHERE asx_code = ?"
        args = (asx_code.upper(),)
    sql += " ORDER BY completed_at DESC LIMIT ?"
    with _lock, _connect() as conn:
        rows = conn.execute(sql, args + (limit,)).fetchall()
    out = []
    for r in rows:
        p = json.loads(r["payload"])
        out.append({
            "runId": p["runId"],
            "company": {"asxCode": p["company"]["asxCode"], "name": p["company"]["name"]},
            "completedAt": p.get("completedAt"),
            "requestedBy": (p.get("requestedBy") or {}).get("name"),
            "pillars": [{"pillar": x["pillar"], "band": x["result"]["band"],
                         "confidence": x["result"]["confidence"],
                         "matrixVersion": x["matrixVersion"]}
                        for x in p.get("pillars", [])],
        })
    return out


def save_request(req: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO disclosure_requests "
            "(request_id, token, asx_code, run_id, status, created_at, due_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (req["requestId"], req["token"], req["company"]["asxCode"], req.get("runId"),
             req["status"], req["createdAt"], req.get("dueAt"), json.dumps(req)),
        )


def get_request(request_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT payload FROM disclosure_requests WHERE request_id = ?",
                           (request_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def get_request_by_token(token: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT payload FROM disclosure_requests WHERE token = ?",
                           (token,)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_requests(asx_code: str | None = None) -> list[dict]:
    sql = "SELECT payload FROM disclosure_requests"
    args: tuple = ()
    if asx_code:
        sql += " WHERE asx_code = ?"
        args = (asx_code.upper(),)
    sql += " ORDER BY created_at DESC"
    with _lock, _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def save_user(user: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO users (user_id, email, payload) VALUES (?, ?, ?)",
                     (user["userId"], user["email"], json.dumps(user)))


def get_user(user_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT payload FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def get_user_by_email(email: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT payload FROM users WHERE email = ?",
                           (email.lower(),)).fetchone()
    return json.loads(row["payload"]) if row else None


def save_session(token_hash: str, user_id: str, expires_at: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO sessions (token_hash, user_id, expires_at) "
                     "VALUES (?, ?, ?)", (token_hash, user_id, expires_at))


def get_session(token_hash: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE token_hash = ?",
                           (token_hash,)).fetchone()
    return {"userId": row["user_id"], "expiresAt": row["expires_at"]} if row else None


def delete_session(token_hash: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
