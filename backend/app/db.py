"""
The relational database.

SQLite on a laptop, PostgreSQL (Amazon RDS) in the deployment design: the same
models run on both, chosen by DATABASE_URL. Tables are created on first use.

Design rule: the issued result of an assessment is kept exactly as the API
returned it (assessment_runs.payload), so a report can always be reproduced.
Everything we need to query, list, join or audit is also stored in proper
columns and child tables: who ran what, the band per pillar, every source
document, every disclosure request and the criteria it asked about.

    users ─┬─< assessment_runs >── companies
           │        ├─< pillar_results
           │        └─< source_documents
           ├─< disclosure_requests >── companies
           │        ├─< request_items
           │        └─< request_documents
           ├─< email_log
           └─< revoked_tokens

See docs/database.md for the full schema.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
from pathlib import Path

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DEFAULT_SQLITE = Path(os.getenv("DB_PATH", "data/platform.db"))


def _url() -> str:
    return os.getenv("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE}"


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="analyst")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class RevokedToken(Base):
    """A signed-out JWT. Kept until it would have expired anyway."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))


class Company(Base):
    """A company we can assess. Listed companies have an ASX code; private
    companies are added by an analyst with a website and a contact address."""
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    website: Mapped[str] = mapped_column(String(300))
    sector: Mapped[str | None] = mapped_column(String(80))
    tier: Mapped[str | None] = mapped_column(String(40))
    listed: Mapped[bool] = mapped_column(Boolean, default=True)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssessmentRun(Base):
    __tablename__ = "assessment_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"),
                                                     index=True)
    status: Mapped[str] = mapped_column(String(20))
    pillars: Mapped[str] = mapped_column(String(80))
    engine: Mapped[str | None] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(60))
    requested_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True),
                                                                   index=True)
    payload: Mapped[dict] = mapped_column(JSON)

    company: Mapped[Company] = relationship()
    pillar_results: Mapped[list[PillarResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan")
    source_documents: Mapped[list[SourceDocument]] = relationship(
        back_populates="run", cascade="all, delete-orphan")


class PillarResult(Base):
    __tablename__ = "pillar_results"
    __table_args__ = (UniqueConstraint("run_id", "pillar"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("assessment_runs.id", ondelete="CASCADE"))
    pillar: Mapped[str] = mapped_column(String(20))
    matrix_version: Mapped[str] = mapped_column(String(40))
    band: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[str | None] = mapped_column(String(2))
    transparency: Mapped[float | None] = mapped_column(Float)
    practice: Mapped[float | None] = mapped_column(Float)
    run: Mapped[AssessmentRun] = relationship(back_populates="pillar_results")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("assessment_runs.id", ondelete="CASCADE"),
                                        index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(20))
    grade: Mapped[str | None] = mapped_column(String(2))
    provenance: Mapped[str] = mapped_column(String(30), default="PUBLIC")
    run: Mapped[AssessmentRun] = relationship(back_populates="source_documents")


class DisclosureRequest(Base):
    __tablename__ = "disclosure_requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("assessment_runs.id",
                                                          ondelete="SET NULL"))
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    contact_email: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(20), index=True)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[dict] = mapped_column(JSON)

    company: Mapped[Company] = relationship()
    items: Mapped[list[RequestItem]] = relationship(cascade="all, delete-orphan")
    documents: Mapped[list[RequestDocument]] = relationship(cascade="all, delete-orphan")


class RequestItem(Base):
    """One criterion a request asked the company about."""
    __tablename__ = "request_items"
    __table_args__ = (UniqueConstraint("request_id", "criterion_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("disclosure_requests.id",
                                                       ondelete="CASCADE"))
    criterion_code: Mapped[str] = mapped_column(String(10))
    pillar: Mapped[str] = mapped_column(String(20))
    status_at_request: Mapped[str] = mapped_column(String(30))


class RequestDocument(Base):
    """A file a company supplied in answer to a request."""
    __tablename__ = "request_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("disclosure_requests.id",
                                                       ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    path: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(80))
    bytes: Mapped[int] = mapped_column(Integer)


class EmailLog(Base):
    """Every email the platform sent or saved, and who sent it."""
    __tablename__ = "email_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(30))
    recipients: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(300))
    delivered: Mapped[bool] = mapped_column(Boolean)
    record_path: Mapped[str | None] = mapped_column(Text)
    sent_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    run_id: Mapped[str | None] = mapped_column(String(40))
    request_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
_Session = None
_lock = threading.RLock()


def engine():
    """Created lazily so tests can point DB_PATH or DATABASE_URL somewhere else first."""
    global _engine, _Session
    with _lock:
        if _engine is None:
            url = _url()
            legacy = None
            if url.startswith("sqlite:///"):
                path = Path(url.removeprefix("sqlite:///"))
                path.parent.mkdir(parents=True, exist_ok=True)
                legacy = _move_legacy(path)
            _engine = create_engine(url, future=True)
            if url.startswith("sqlite"):
                @event.listens_for(_engine, "connect")
                def _fk_on(conn, _record):
                    conn.execute("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(_engine)
            _Session = sessionmaker(_engine, expire_on_commit=False)
            if legacy:
                _import_legacy(legacy)
    return _engine


def _move_legacy(path: Path) -> Path | None:
    """Earlier versions kept JSON blobs in a 'runs' table. Move that file aside
    so the relational schema starts clean, and return it for importing."""
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "runs" not in names or "assessment_runs" in names:
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    moved = path.with_name(f"{path.stem}.legacy-{stamp}{path.suffix}")
    path.rename(moved)
    return moved


def _import_legacy(path: Path) -> None:
    """Carry runs, requests and accounts from the old file into the new tables."""
    from . import store

    with sqlite3.connect(path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        users = conn.execute("SELECT payload FROM users").fetchall() if "users" in names else []
        runs = conn.execute("SELECT payload FROM runs").fetchall()
        reqs = (conn.execute("SELECT payload FROM disclosure_requests").fetchall()
                if "disclosure_requests" in names else [])
    counts = {"accounts": 0, "runs": 0, "requests": 0}
    for key, rows, save in (("accounts", users, store.save_user), ("runs", runs, store.save_run),
                            ("requests", reqs, store.save_request)):
        for (p,) in rows:
            try:
                save(json.loads(p))
                counts[key] += 1
            except Exception as exc:  # noqa: BLE001 - one bad old row must not block startup
                print(f"  Skipped one legacy {key[:-1]}: {exc}", flush=True)
    print(f"  Imported {counts['runs']} runs, {counts['requests']} requests and "
          f"{counts['accounts']} accounts "
          f"from {path.name} into the relational database", flush=True)


def session():
    engine()
    return _Session()


def reset(url: str | None = None) -> None:
    """Point at a different database. For tests."""
    global _engine, _Session
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine, _Session = None, None
        if url:
            os.environ["DATABASE_URL"] = url
