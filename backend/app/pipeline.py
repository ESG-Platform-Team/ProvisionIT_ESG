"""
The assessment run, end to end.

This is sequence diagram 1 as code: harvest, extract, choose OCR or not, run the
model per principle, score deterministically, aggregate, complete.

One harvest feeds every pillar. The governance statement, the annual report and
the sustainability report are fetched once and read three ways, which keeps the
request count against a company's website the same whether one pillar or three
is assessed.

For the MVP it runs inside one background task rather than through a queue and a
state machine. Step Functions, SQS and the scheduler stay on the architecture
diagram as the deployment target.
"""

from __future__ import annotations

import datetime
import hashlib
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from . import harvest, llm, pillars, scoring, textract

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


# Mick, client meeting 7 September: the machine may form the interpretation,
# provided the output says plainly that a machine formed it. This text travels
# with every result, on screen, in the JSON and on the first page of the PDF.
def interpretation_statement(engine: str, model: str | None) -> str:
    reader = (f"A language model ({model})" if engine == "LLM" and model
              else "A language model" if engine == "LLM"
              else "Keyword-matching software")
    return (
        "This assessment was formed by software, not by a person. "
        f"{reader} read the documents listed in the source log and reported what "
        "they say, with a quoted passage and a page reference for each finding. "
        "Fixed rules in code then applied the criteria matrix to produce every "
        "status, band and grade shown. No analyst has reviewed or adjusted these "
        "findings unless a finding is marked as overridden. Provision IT expresses "
        "no opinion on the company; the interpretation is the machine's and the "
        "judgement is yours."
    )


KEYWORD_ONLY_NOTE = (
    "No language model was available for this run. Findings come from keyword "
    "matching only, so every finding is capped at STATED and should be read as "
    "evidence that a topic is mentioned, not that a practice exists."
)


class RunState:
    """Progress the frontend polls. Mirrors the contract's running response."""

    def __init__(self, run_id: str, company: dict, pillar_keys: list[str] | None = None) -> None:
        self.run_id = run_id
        self.company = company
        self.pillars = pillar_keys or ["GOVERNANCE"]
        self.status = "QUEUED"
        self.stage = "QUEUED"
        self.progress = 0.0
        self.source_log: list[dict] = []
        self.error: str | None = None
        self.started_at = time.time()
        self.completed_at: float | None = None
        self.log_lines: list[str] = []

    def log(self, line: str) -> None:
        self.log_lines.append(line)
        print(f"  {line}", flush=True)


async def run_assessment(
    company: dict, state: RunState, use_llm: bool = True,
    api_key: str | None = None, max_docs: int = 20,
    pillar_keys: list[str] | None = None,
    extra_documents: list[dict] | None = None,
    disclosure_requests: list[dict] | None = None,
) -> dict:
    """extra_documents are files a company supplied in answer to a disclosure
    request: dicts with title, path, mediaType and requestId. They are read and
    graded like any other source and recorded in the source log as provided on
    request, so a reader can always tell them apart from public documents.

    disclosure_requests are summaries of requests made for this company. They
    annotate the criteria they asked about, so a criterion that is still a gap
    because the company did not answer says so."""
    keys = pillars.normalise(pillar_keys or state.pillars)
    state.pillars = keys
    state.status = "RUNNING"

    async with harvest.new_client() as client:
        # --- Stage 1, discovery -------------------------------------------
        state.stage = "HARVEST"
        state.log(f"Discovering disclosure documents on {company['website']}")
        hv = harvest.Harvester(max_docs=max_docs)

        candidates = await hv.discover(client, company["website"])
        for url in company.get("extraUrls") or []:
            candidates.append({
                "url": url, "source_type": _guess_type(url),
                "title": harvest._title_from_url(url),
                "is_pdf": url.lower().endswith(".pdf"),
            })
        state.log(f"Found {len(candidates)} candidate documents")
        state.progress = 0.1

        # --- Stage 2, fetch and extract -----------------------------------
        documents: list[dict] = []
        texts: list[tuple[str, list[str], str]] = []
        titles_seen: dict[str, int] = {}

        total = len(candidates) + len(extra_documents or [])
        for i, cand in enumerate(candidates):
            task, doc = await hv.fetch(client, cand["url"], cand["source_type"], cand["title"])
            entry = _entry(cand["title"], cand["url"], cand["source_type"],
                           _short_location(cand["url"]), task.status)
            entry.update({"httpStatus": task.http_status, "elapsedMs": task.elapsed_ms,
                          "robotsAllowed": task.robots_allowed, "note": task.note})
            if doc is not None:
                _read(doc, entry, cand["source_type"], texts, titles_seen)
            documents.append(entry)
            state.source_log = documents
            state.progress = 0.1 + 0.3 * ((i + 1) / max(1, total))
            _log_doc(state, entry)

        for extra in extra_documents or []:
            doc = _local_document(extra)
            entry = _entry(extra["title"], doc.url if doc else "", "company_response",
                           "provided on request", "RETRIEVED" if doc else "NOT_FOUND")
            entry.update({"provenance": "PROVIDED_ON_REQUEST",
                          "requestId": extra.get("requestId"),
                          "robotsAllowed": None, "elapsedMs": 0,
                          "note": "Supplied by the company in answer to a disclosure request"})
            if doc is not None:
                _read(doc, entry, "company_response", texts, titles_seen)
            documents.append(entry)
            state.source_log = documents
            _log_doc(state, entry)

    readable = [d for d in documents if d["outcome"] == "RETRIEVED"]
    state.log(f"{len(readable)} of {len(documents)} sources yielded text")

    # --- Stage 3, extraction, one pass per pillar -------------------------
    state.stage = "EXTRACT"
    client_llm = llm.GeminiClient(api_key=api_key) if use_llm else None
    if client_llm and not client_llm.configured:
        state.log("GEMINI_API_KEY not set, falling back to keyword extraction")
        client_llm = None

    by_title = {d["title"]: d for d in readable}
    units_total = sum(len(pillars.get(k)["principles"]) for k in keys)
    units_done = 0
    pillar_results: list[dict] = []

    async with harvest.new_client() as client:
        for key in keys:
            spec = pillars.get(key)
            findings_by_code: dict[str, dict] = {}
            finding_source: dict[str, dict] = {}
            retrieval_failed: set[str] = set()

            for principle in spec["principles"]:
                units_done += 1
                keywords = [k for c in principle["criteria"] for k in c["keywords"]]
                passages: list[tuple[str, int, str]] = []
                for title, pages, _ in texts:
                    for page_no, chunk in textract.windows_for(pages, keywords):
                        passages.append((title, page_no, chunk))

                label = f"{spec['label']} {principle['number']}"
                if not passages:
                    for c in principle["criteria"]:
                        retrieval_failed.add(c["criterionCode"])
                    state.log(f"{label}: no relevant passages found")
                    state.progress = 0.4 + 0.55 * units_done / max(1, units_total)
                    continue

                if client_llm:
                    chars = sum(len(t) for _, _, t in passages)
                    state.log(f"{label}: {len(passages)} passages, {chars:,} chars to Gemini")
                    try:
                        raw = await client_llm.extract_principle(
                            client, principle, passages, spec["matrixVersion"],
                            spec["frameworkName"], spec["unitName"],
                        )
                    except RuntimeError as exc:
                        state.log(f"{label}: {exc}")
                        raw = llm.keyword_findings(principle, passages)
                else:
                    raw = llm.keyword_findings(principle, passages)

                for f in raw:
                    code = f.get("criterionCode")
                    if code:
                        findings_by_code[code] = f
                        finding_source[code] = _origin(f, passages, by_title)
                state.progress = 0.4 + 0.55 * units_done / max(1, units_total)

            # --- Stage 4, deterministic scoring ---------------------------
            state.stage = "SCORE"
            scored = scoring.score_run(findings_by_code, documents, retrieval_failed,
                                       spec["principles"])
            engine = "LLM" if client_llm else "KEYWORD"
            model = client_llm.model_used if client_llm else None
            for principle in scored["principles"]:
                for row in principle["criteria"]:
                    _finish_row(row, finding_source.get(row["criterionCode"], {}),
                                engine, model, disclosure_requests or [])
            pillar_results.append({
                "pillar": spec["pillar"], "label": spec["label"],
                "matrixVersion": spec["matrixVersion"],
                "frameworkEdition": spec["frameworkEdition"],
                "frameworkName": spec["frameworkName"],
                "unitName": spec["unitName"], "draft": spec["draft"],
                "result": scored["result"], "principles": scored["principles"],
            })

    if client_llm:
        state.log(f"Gemini calls: {client_llm.calls_made}, cache hits: {client_llm.cache_hits}")

    state.stage = "AGGREGATE"
    state.progress = 0.98
    return _assemble(company, state, pillar_results, documents,
                     engine="LLM" if client_llm else "KEYWORD",
                     model=client_llm.model_used if client_llm else None,
                     disclosure_requests=disclosure_requests or [])


def _entry(title, url, source_type, location, outcome) -> dict:
    return {
        "sourceDocumentId": None, "title": title, "location": location, "url": url,
        "sourceType": source_type, "outcome": outcome, "httpStatus": None,
        "elapsedMs": None, "robotsAllowed": None, "note": "", "sourceGrade": None,
        "extractionMethod": None, "contentHash": None, "pages": 0,
        "provenance": "PUBLIC",
    }


def _read(doc, entry, source_type, texts, titles_seen) -> None:
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
        return

    # Titles label passages for the model and link findings back to documents,
    # so they have to be unique within a run. Two links both called "Download"
    # would otherwise attribute evidence to the wrong file.
    title = entry["title"] or "Untitled document"
    n = titles_seen.get(title, 0) + 1
    titles_seen[title] = n
    if n > 1:
        title = f"{title} ({n})"
        entry["title"] = title

    entry["sourceGrade"] = scoring.grade_for(source_type, method)
    _persist(doc)
    texts.append((title, pages, source_type))


def _log_doc(state, entry) -> None:
    pages = f"{entry['pages']}p" if entry["pages"] else ""
    state.log(f"{entry['outcome']:<11} {entry['title'][:52]:<54} {pages:>5}")


def _origin(finding: dict, passages, by_title: dict) -> dict:
    """Which document a finding came from. The model names the source title and
    page from the passage header; fall back to the page alone if it did not."""
    title = (finding.get("sourceTitle") or "").strip()
    if title in by_title:
        return by_title[title]
    page = finding.get("page") or 0
    for t, p, _ in passages:
        if p == page and t in by_title:
            return by_title[t]
    return {}


def _finish_row(row: dict, origin: dict, engine: str, model: str | None,
                requests: list[dict]) -> None:
    # The grade lives on the document, which is why this is a second pass and
    # not a field on the finding.
    for ev in row["evidence"]:
        ev["sourceGrade"] = origin.get("sourceGrade")
        ev["sourceDocumentId"] = origin.get("sourceDocumentId")
        ev["provenance"] = origin.get("provenance", "PUBLIC")
        if origin.get("title"):
            ev["locator"] = f"{origin['title'][:40]} {ev['locator']}"
    if row["maturity"] is not None and row["evidence"]:
        grade = row["evidence"][0]["sourceGrade"]
        row["notation"] = f"{row['maturity']}{grade}" if grade else None

    row["interpretedBy"] = {"method": "MACHINE", "engine": engine, "model": model}

    for req in requests:
        if row["criterionCode"] in req.get("criteria", []):
            row["disclosureRequest"] = {
                "requestId": req["requestId"], "status": req["status"],
                "sentAt": req.get("sentAt"), "dueAt": req.get("dueAt"),
                "respondedAt": req.get("respondedAt"),
                "note": _request_note(req, row["status"]),
            }


def _request_note(req: dict, row_status: str) -> str:
    """How a request bears on one criterion. The criterion's own status is never
    changed by an unanswered request; the note says what it now means."""
    day = lambda k: (req.get(k) or "")[:10]  # noqa: E731
    sent = day("sentAt")
    if req["status"] == "SENT":
        return f"Requested from the company on {sent}, response due {day('dueAt')}"
    if req["status"] == "RESPONDED":
        return f"Company responded on {day('respondedAt')}"
    outcome = ("so it is reported as insufficient information" if row_status == "EVIDENCE_GAP"
               else "and it remains not disclosed" if row_status == "NOT_DISCLOSED"
               else "")
    if req["status"] == "DECLINED":
        return f"Requested on {sent}, the company declined on {day('respondedAt')}, {outcome}".rstrip(", ")
    if req["status"] == "NO_RESPONSE":
        closed = day("closedAt")
        when = (f"no response by the due date {day('dueAt')}" if closed >= day("dueAt")
                else f"closed without a response on {closed}")
        return f"Requested on {sent}, {when}, {outcome}".rstrip(", ")
    return ""


def _assemble(company, state, pillar_results, documents, engine, model,
              disclosure_requests) -> dict:
    state.status = "COMPLETE"
    state.stage = "COMPLETE"
    state.progress = 1.0
    state.completed_at = time.time()
    generated = _iso(state.completed_at)
    for p in pillar_results:
        p["result"]["generatedAt"] = generated
        p["result"]["peerContext"] = {"matrixVersion": p["matrixVersion"], "peerCount": 0,
                                      "transparencyPercentile": None,
                                      "practicePercentile": None}

    primary = pillar_results[0]
    return {
        "runId": state.run_id,
        "status": "COMPLETE",
        "trigger": "MANUAL",
        "requestedAt": _iso(state.started_at),
        "completedAt": generated,
        "company": company,
        "pillarsRequested": [p["pillar"] for p in pillar_results],
        "pillars": pillar_results,
        # The first pillar is repeated at the top level so a contract v0.1
        # client that only knows governance keeps working unchanged.
        "frameworkEdition": primary["frameworkEdition"],
        "matrixVersion": primary["matrixVersion"],
        "result": primary["result"],
        "principles": primary["principles"],
        "interpretation": {
            "method": "MACHINE",
            "engine": engine,
            "model": model,
            "statement": interpretation_statement(engine, model),
            "note": KEYWORD_ONLY_NOTE if engine == "KEYWORD" else None,
            "humanReviewed": False,
        },
        "disclosureRequests": disclosure_requests,
        "sourceLog": documents,
        "runLog": state.log_lines,
    }


def _local_document(extra: dict):
    path = Path(extra["path"])
    if not path.exists():
        return None
    content = path.read_bytes()
    media = extra.get("mediaType") or (
        "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
        if path.suffix.lower() in (".html", ".htm") else "text/plain")
    return harvest.SourceDocument(
        url=f"request://{extra.get('requestId', 'unknown')}/{path.name}",
        source_type="company_response", title=extra["title"], media_type=media,
        content=content, content_hash=hashlib.sha256(content).hexdigest(),
        retrieved_at=time.time(), publisher="provided by the company",
    )


def _persist(doc) -> None:
    ext = ".pdf" if "pdf" in doc.media_type else ".html"
    path = RAW_DIR / f"{doc.content_hash}{ext}"
    if not path.exists():
        path.write_bytes(doc.content)


def _guess_type(url: str) -> str:
    low = url.lower()
    for source_type, pattern in harvest.DOC_PATTERNS:
        if re.search(pattern, low):
            return source_type
    return "webpage"


def _short_location(url: str) -> str:
    p = urlparse(url)
    path = p.path if len(p.path) < 46 else p.path[:43] + "..."
    return f"{p.netloc}{path}"


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:20]}"
