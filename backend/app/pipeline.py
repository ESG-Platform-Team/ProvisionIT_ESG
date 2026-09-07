"""
The assessment run, end to end.

This is sequence diagram 1 as code: harvest, extract, choose OCR or not, run the
model per principle, score deterministically, aggregate, complete.

For the MVP it runs synchronously inside one background task rather than through
a queue and a state machine. Step Functions, SQS and the scheduler stay on the
architecture diagram as the deployment target. Adding them now would multiply the
debugging surface for no visible gain in a two week build.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from pathlib import Path

from . import harvest, llm, scoring, textract
from .matrix import FRAMEWORK_EDITION, MATRIX_VERSION, PRINCIPLES

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


class RunState:
    """Progress the frontend polls. Mirrors the contract's running response."""

    def __init__(self, run_id: str, company: dict) -> None:
        self.run_id = run_id
        self.company = company
        self.status = "QUEUED"
        self.stage = "QUEUED"
        self.progress = 0.0
        self.source_log: list[dict] = []
        self.document: dict | None = None
        self.error: str | None = None
        self.started_at = time.time()
        self.completed_at: float | None = None
        self.log_lines: list[str] = []

    def log(self, line: str) -> None:
        self.log_lines.append(line)
        print(f"  {line}", flush=True)


async def run_assessment(
    company: dict, state: RunState, use_llm: bool = True,
    api_key: str | None = None, max_docs: int = 12,
) -> dict:
    state.status = "RUNNING"

    async with harvest.new_client() as client:
        # --- Stage 1, discovery -------------------------------------------
        state.stage = "HARVEST"
        state.log(f"Discovering governance documents on {company['website']}")
        hv = harvest.Harvester(max_docs=max_docs)

        candidates = await hv.discover(client, company["website"])
        if company.get("extraUrls"):
            for url in company["extraUrls"]:
                candidates.append({
                    "url": url, "source_type": _guess_type(url),
                    "title": harvest._title_from_url(url),
                    "is_pdf": url.lower().endswith(".pdf"),
                })
        state.log(f"Found {len(candidates)} candidate documents")
        state.progress = 0.15

        # --- Stage 2, fetch and extract -----------------------------------
        documents: list[dict] = []
        texts: list[tuple[str, list[str], str]] = []

        for i, cand in enumerate(candidates):
            task, doc = await hv.fetch(client, cand["url"], cand["source_type"], cand["title"])
            entry = {
                "sourceDocumentId": None,
                "title": cand["title"],
                "location": _short_location(cand["url"]),
                "url": cand["url"],
                "sourceType": cand["source_type"],
                "outcome": task.status,
                "httpStatus": task.http_status,
                "elapsedMs": task.elapsed_ms,
                "robotsAllowed": task.robots_allowed,
                "note": task.note,
                "sourceGrade": None,
                "extractionMethod": None,
                "contentHash": None,
                "pages": 0,
            }

            if doc is not None:
                text, pages, method = textract.extract(doc)
                doc.text, doc.pages = text, pages
                entry["contentHash"] = doc.content_hash
                entry["extractionMethod"] = method
                entry["pages"] = len(pages)
                entry["sourceDocumentId"] = f"doc_{doc.short_hash}"

                if method in ("failed", "scanned_no_ocr", "unsupported") or not text.strip():
                    entry["outcome"] = "UNREADABLE"
                    entry["note"] = {
                        "scanned_no_ocr": "Image-only PDF, no OCR available locally",
                        "failed": "Could not parse the document",
                        "unsupported": "Unsupported media type",
                    }.get(method, "No text recovered")
                else:
                    entry["sourceGrade"] = scoring.grade_for(cand["source_type"], method)
                    _persist(doc)
                    texts.append((cand["title"], pages, cand["source_type"]))

            documents.append(entry)
            state.source_log = documents
            state.progress = 0.15 + 0.35 * ((i + 1) / max(1, len(candidates)))
            state.log(
                f"{entry['outcome']:<11} {cand['title'][:52]:<54} "
                f"{(str(entry['pages']) + 'p') if entry['pages'] else '':>5}"
            )

        readable = [d for d in documents if d["outcome"] == "RETRIEVED"]
        state.log(f"{len(readable)} of {len(documents)} sources yielded text")

        if not readable:
            state.stage = "AGGREGATE"
            scored = scoring.score_run({}, documents, set())
            return _assemble(company, state, scored, documents, [])

        # --- Stage 3, extraction ------------------------------------------
        state.stage = "EXTRACT"
        client_llm = llm.GeminiClient(api_key=api_key) if use_llm else None
        if client_llm and not client_llm.configured:
            state.log("GEMINI_API_KEY not set, falling back to keyword extraction")
            client_llm = None

        findings_by_code: dict[str, dict] = {}
        finding_source: dict[str, dict] = {}
        retrieval_failed: set[str] = set()

        for idx, principle in enumerate(PRINCIPLES):
            keywords = [k for c in principle["criteria"] for k in c["keywords"]]
            passages: list[tuple[str, int, str]] = []
            passage_origin: dict[int, dict] = {}

            for title, pages, source_type in texts:
                for page_no, chunk in textract.windows_for(pages, keywords):
                    passages.append((title, page_no, chunk))
                    doc_entry = next(
                        (d for d in readable if d["title"] == title), None
                    )
                    passage_origin[page_no] = doc_entry or {}

            if not passages:
                for c in principle["criteria"]:
                    retrieval_failed.add(c["criterionCode"])
                state.log(f"Principle {principle['number']}: no relevant passages found")
                state.progress = 0.5 + 0.4 * ((idx + 1) / len(PRINCIPLES))
                continue

            chars = sum(len(t) for _, _, t in passages)
            if client_llm:
                state.log(
                    f"Principle {principle['number']}: {len(passages)} passages, "
                    f"{chars:,} chars to Gemini"
                )
                try:
                    raw = await client_llm.extract_principle(
                        client, principle, passages, MATRIX_VERSION
                    )
                except RuntimeError as exc:
                    state.log(f"Principle {principle['number']}: {exc}")
                    raw = llm.keyword_findings(principle, passages)
            else:
                raw = llm.keyword_findings(principle, passages)

            for f in raw:
                code = f.get("criterionCode")
                if code:
                    findings_by_code[code] = f
                    finding_source[code] = passage_origin.get(f.get("page", 0), {})

            state.progress = 0.5 + 0.4 * ((idx + 1) / len(PRINCIPLES))

        if client_llm:
            state.log(
                f"Gemini calls: {client_llm.calls_made}, cache hits: {client_llm.cache_hits}"
            )

        # --- Stage 4, deterministic scoring -------------------------------
        state.stage = "SCORE"
        scored = scoring.score_run(findings_by_code, documents, retrieval_failed)

        # Attach the source grade and document id to each evidence record. The
        # grade lives on the document, which is why this is a second pass and
        # not a field on the finding.
        for row in scored["criterionResults"]:
            origin = finding_source.get(row["criterionCode"], {})
            for ev in row["evidence"]:
                ev["sourceGrade"] = origin.get("sourceGrade")
                ev["sourceDocumentId"] = origin.get("sourceDocumentId")
                if origin.get("title"):
                    ev["locator"] = f"{origin['title'][:40]} {ev['locator']}"
            if row["maturity"] is not None and row["evidence"]:
                grade = row["evidence"][0]["sourceGrade"]
                row["notation"] = f"{row['maturity']}{grade}" if grade else None

        state.stage = "AGGREGATE"
        state.progress = 0.98
        return _assemble(company, state, scored, documents, texts)


def _assemble(company, state, scored, documents, texts) -> dict:
    state.status = "COMPLETE"
    state.stage = "COMPLETE"
    state.progress = 1.0
    state.completed_at = time.time()

    return {
        "runId": state.run_id,
        "status": "COMPLETE",
        "trigger": "MANUAL",
        "requestedAt": _iso(state.started_at),
        "completedAt": _iso(state.completed_at),
        "frameworkEdition": FRAMEWORK_EDITION,
        "matrixVersion": MATRIX_VERSION,
        "company": company,
        "result": {**scored["result"], "generatedAt": _iso(state.completed_at),
                   "peerContext": {"matrixVersion": MATRIX_VERSION, "peerCount": 0,
                                   "transparencyPercentile": None,
                                   "practicePercentile": None}},
        "principles": scored["principles"],
        "sourceLog": documents,
        "runLog": state.log_lines,
    }


def _persist(doc) -> None:
    ext = ".pdf" if "pdf" in doc.media_type else ".html"
    path = RAW_DIR / f"{doc.content_hash}{ext}"
    if not path.exists():
        path.write_bytes(doc.content)


def _guess_type(url: str) -> str:
    low = url.lower()
    for source_type, pattern in harvest.DOC_PATTERNS:
        import re
        if re.search(pattern, low):
            return source_type
    return "webpage"


def _short_location(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    path = p.path if len(p.path) < 46 else p.path[:43] + "..."
    return f"{p.netloc}{path}"


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:20]}"
