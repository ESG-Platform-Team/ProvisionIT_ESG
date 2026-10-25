#!/usr/bin/env python3
"""Acceptance tests: one block per user story, run end to end through the API.

Each block is named after its story on the Confluence "User story" page
(US-01 ...) and states its acceptance criterion as Given / When / Then. The
whole journey runs offline against the fixture company TST: a local copy of
fixture-site is served on port 8123, the reader is keyword matching (no API
key), and email goes to the local outbox (no SMTP), so nothing leaves the
machine.

Set ACCEPTANCE_REPORT=path.json to also write a machine-readable result per
story; CI uploads it as the acceptance evidence for the test plan.
"""

import functools
import http.server
import io
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

from testkit import check, done, section

HERE = Path(__file__).parent
TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'acceptance.db'}"
os.environ["JWT_SECRET"] = "acceptance-test-secret-long-enough-for-hs256"
os.environ["MAIL_DIR"] = str(TMP / "mail")
os.environ["RESPONSE_DIR"] = str(TMP / "responses")
for key in ("SMTP_HOST", "GEMINI_API_KEY", "AUTH_REQUIRED", "LLM_REPLAY", "SIGNUP_DOMAINS"):
    os.environ.pop(key, None)

from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from app import scoring  # noqa: E402
from app.main import app  # noqa: E402

RESULTS: list[dict] = []
_current: dict = {}


def story(story_id: str, title: str, criterion: str):
    """Start a user story block. Every check until the next story counts toward it."""
    _current.clear()
    _current.update(id=story_id, title=title, criterion=criterion, checks=[])
    RESULTS.append(_current.copy())
    section(f"{story_id}  {title}\n      {criterion}")


def verify(name: str, condition: bool, detail: str = ""):
    check(f"{RESULTS[-1]['id']}: {name}", condition, detail)
    RESULTS[-1]["checks"].append({"check": name, "passed": bool(condition)})


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def wait_for_run(client, run_id: str, headers: dict, timeout: float = 90) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/assessments/{run_id}", headers=headers).json()
        if run.get("status") in ("COMPLETE", "FAILED"):
            return run
        time.sleep(0.3)
    raise TimeoutError(f"run {run_id} did not finish in {timeout}s")


def criteria(run: dict, pillar: str | None = None):
    for p in run["pillars"]:
        if pillar and p["pillar"] != pillar:
            continue
        for principle in p["principles"]:
            yield from principle["criteria"]


# The fixture company's website is fixed at localhost:8123 (app/companies.py).
server = None
if _port_free(8123):
    handler = functools.partial(_Quiet, directory=str(HERE / "fixture-site"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8123), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
else:
    print("  note  port 8123 is in use; assuming the fixture site is already served there")

with TestClient(app) as client:
    # ------------------------------------------------------------------ access
    story("US-36", "Only signed-in analysts can use the platform",
          "Given no sign-in, when the API is called, then it refuses; "
          "given a new account, then the same call succeeds.")
    verify("the API refuses a request with no token",
           client.get("/api/assessments").status_code == 401)
    signup = client.post("/api/auth/signup", json={
        "name": "Sarah Lee", "email": "sarah.lee@example.com", "password": "a long test password"})
    verify("an analyst can create an account", signup.status_code == 201)
    H = {"Authorization": f"Bearer {signup.json()['token']}"}
    verify("with the token the API answers", client.get("/api/assessments", headers=H).status_code == 200)

    # ---------------------------------------------------------- search, gather
    story("US-04", "Resolve a name or ASX code to one company",
          "Given the ASX code TST, when the analyst searches, then exactly one company is "
          "returned with its legal name and website before anything is gathered.")
    found = client.get("/api/companies?q=TST", headers=H).json()
    matches = found.get("matches", found if isinstance(found, list) else [])
    tst = [m for m in matches if m.get("asxCode") == "TST"]
    verify("exactly one company matches TST", len(tst) == 1, str(matches)[:200])
    verify("the match carries a name and website", bool(tst and tst[0].get("name") and tst[0].get("website")))
    nothing = client.get("/api/companies?q=ZZZZ-NOT-A-COMPANY", headers=H).json()
    verify("an unknown code returns no match rather than a guess",
           not nothing.get("matches", nothing if isinstance(nothing, list) else []))

    started = client.post("/api/assessments", headers=H,
                          json={"asxCode": "TST", "pillars": ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"]})
    run = wait_for_run(client, started.json()["runId"], H)
    run_id = run["runId"]
    log = run["sourceLog"]

    story("US-05", "Gather only from approved free public sources",
          "Given a company website, when documents are gathered, then every source is on that "
          "company's own public site, robots.txt is respected and nothing is marked non-public.")
    verify("the assessment completed", run["status"] == "COMPLETE", run.get("status", ""))
    verify("every source comes from the company's own website",
           all(s["url"].startswith("http://localhost:8123/") for s in log))
    verify("no source is under the path robots.txt disallows",
           not any("/private/" in s["url"] for s in log))
    verify("every public source is labelled PUBLIC", all(s["provenance"] == "PUBLIC" for s in log))

    story("US-06", "See which sources were retrieved, failed or unreadable",
          "Given a site with a broken link, when the run finishes, then the source log lists every "
          "attempt with its outcome, and failures are counted rather than dropped.")
    outcomes = {s["outcome"] for s in log}
    verify("successful retrievals are listed", "RETRIEVED" in outcomes)
    failed = [s for s in log if s["outcome"] != "RETRIEVED"]
    verify("failed retrievals stay in the log with a reason",
           bool(failed) and all(s.get("note") for s in failed), str(failed)[:200])
    counts = run["pillars"][0]["result"]["counts"]
    verify("attempted and retrieved are counted separately",
           counts["sourcesAttempted"] > counts["sourcesRetrieved"])

    # ------------------------------------------------------- assessment rules
    story("US-07", "Rate each criterion on a defined maturity scale",
          "Given a disclosed criterion, then it carries a maturity from 0 to 4 with its label, "
          "so a published charter and a bare claim are scored differently.")
    disclosed = [c for c in criteria(run) if c["status"] == "DISCLOSED"]
    verify("disclosed criteria exist", bool(disclosed))
    verify("each disclosed criterion has maturity 0–4 and a label",
           all(isinstance(c["maturity"], int) and 0 <= c["maturity"] <= 4 and c["maturityLabel"]
               for c in disclosed))

    story("US-08", "Missing information is not a zero",
          "Given a criterion with nothing found, then it is reported as a named status with no "
          "maturity value, never as maturity 0.")
    missing = [c for c in criteria(run) if c["status"] != "DISCLOSED"]
    verify("criteria with no evidence exist in this run", bool(missing))
    verify("every missing criterion has maturity null, not 0",
           all(c["maturity"] is None for c in missing))
    allowed = {"DISCLOSED", "EXPLAINED_DEPARTURE", "NOT_DISCLOSED", "NOT_APPLICABLE", "EVIDENCE_GAP"}
    verify("only the five agreed statuses are used",
           {c["status"] for c in criteria(run)} <= allowed)

    story("US-09", "Transparency and Practice are separate results",
          "Given any rated pillar, then Transparency and Practice are reported as two figures "
          "with different units, and no combined number exists.")
    gov = run["pillars"][0]["result"]
    verify("both figures are present", "transparencyScore" in gov and "practiceScore" in gov)
    verify("they use different units",
           gov["transparencyScore"]["unit"] != gov["practiceScore"]["unit"])
    verify("no combined or overall score field exists",
           not any(k in gov for k in ("overallScore", "combinedScore", "score")))

    story("US-10", "Source confidence is shown separately from the result",
          "Given the same findings from a weaker source, then the band and both scores are "
          "unchanged and only the confidence letter differs.")
    principles = scoring.governance_principles() if hasattr(scoring, "governance_principles") else None
    if principles is None:
        from app import pillars
        principles = pillars.get("GOVERNANCE")["principles"]
    first = principles[0]["criteria"][0]["criterionCode"]
    finding = {first: {"criterionCode": first, "found": True, "explainedDeparture": False,
                       "maturitySignal": "STATED", "rationale": "", "excerpt": "x", "page": 1,
                       "confidence": 0.5}}
    strong = scoring.score_run(finding, [{"outcome": "RETRIEVED", "sourceGrade": "A"}], set(), principles)
    weak = scoring.score_run(finding, [{"outcome": "RETRIEVED", "sourceGrade": "D"}], set(), principles)
    verify("the band does not move with source grade",
           strong["result"]["band"] == weak["result"]["band"])
    verify("practice does not move with source grade",
           strong["result"]["practiceScore"]["value"] == weak["result"]["practiceScore"]["value"])
    verify("the confidence letter is its own field", "confidence" in gov and len(gov["confidence"]) == 1)

    story("US-11", "Thin evidence is labelled, not rated",
          "Given coverage below the 55% threshold, then the result is INSUFFICIENT_EVIDENCE with "
          "null scores and a stated reason, and it is still stored.")
    thin = scoring.score_run({}, [{"outcome": "RETRIEVED", "sourceGrade": "B"}],
                             {c["criterionCode"] for p in principles for c in p["criteria"]}, principles)
    verify("the band is INSUFFICIENT_EVIDENCE", thin["result"]["band"] == "INSUFFICIENT_EVIDENCE")
    verify("no score is invented", thin["result"]["practiceScore"]["value"] is None)
    verify("the reason is stated", bool(thin["result"].get("declineReason")))

    story("US-12", "Every company is assessed the same way",
          "Given the same documents, when the company is assessed twice, then every criterion "
          "gets the same status and maturity and the band is identical.")
    again = wait_for_run(client, client.post(
        "/api/assessments", headers=H,
        json={"asxCode": "TST", "pillars": ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"]}).json()["runId"], H)
    verify("the bands match", [p["result"]["band"] for p in again["pillars"]]
           == [p["result"]["band"] for p in run["pillars"]])
    verify("every criterion matches", [(c["status"], c["maturity"]) for c in criteria(again)]
           == [(c["status"], c["maturity"]) for c in criteria(run)])

    story("US-13", "The matrix version is recorded with every assessment",
          "Given any run, then each pillar names the matrix version it was scored against, "
          "and draft matrices say they are drafts.")
    verify("each pillar carries a matrix version", all(p["matrixVersion"] for p in run["pillars"]))
    verify("governance is final, E and S are marked draft",
           [p["draft"] for p in run["pillars"]] == [False, True, True])

    # ---------------------------------------------------- evidence trail
    story("US-14", "Every claim links back to its source",
          "Given a disclosed criterion, then each piece of evidence names a source document that "
          "is in the run's source log with its URL.")
    ids = {s["sourceDocumentId"]: s for s in log if s.get("sourceDocumentId")}
    evidence = [e for c in disclosed for e in c["evidence"]]
    verify("disclosed criteria carry evidence", bool(evidence))
    verify("every piece of evidence points at a logged source with a URL",
           all(e["sourceDocumentId"] in ids and ids[e["sourceDocumentId"]]["url"] for e in evidence))

    story("US-16", "The exact passage and its page are stored",
          "Given a finding, when the analyst opens its evidence, then the quoted passage and a "
          "page locator come back from the stored run.")
    code = disclosed[0]["criterionCode"]
    ev = client.get(f"/api/assessments/{run_id}/criteria/{code}/evidence", headers=H)
    body = json.dumps(ev.json())
    verify("the evidence endpoint answers", ev.status_code == 200)
    verify("it returns the excerpt", disclosed[0]["evidence"][0]["excerpt"][:40] in body)
    verify("it returns a page locator", all(e.get("page") and e.get("locator") for e in evidence))

    story("US-15", "Source authority is recorded apart from retrieval",
          "Given a retrieved document, then its source grade, source type and retrieval outcome "
          "are separate fields.")
    retrieved = [s for s in log if s["outcome"] == "RETRIEVED"]
    verify("every retrieved source has a grade A–E", all(s["sourceGrade"] in "ABCDE" for s in retrieved))
    verify("source type and outcome are separate fields", all(s["sourceType"] and s["outcome"] for s in retrieved))

    # ----------------------------------------------------------- outputs
    story("US-17", "An on-screen summary with evidence and limits",
          "Given a finished run, then each pillar has a band, confidence letter, both scores and "
          "coverage counts, and the run carries a plain statement of how it was formed.")
    verify("each pillar has band, confidence, both scores and counts",
           all({"band", "confidence", "transparencyScore", "practiceScore", "counts"} <= set(p["result"])
               for p in run["pillars"]))
    verify("the run explains how it was formed", bool(run["interpretation"]["statement"]))

    story("US-24", "Governance, Environmental and Social in one run",
          "Given all three pillars are chosen, when one run completes, then it holds three "
          "separate results that are never merged.")
    verify("three pillars in the requested order",
           [p["pillar"] for p in run["pillars"]] == ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"])
    verify("each pillar has its own result", len({id(p["result"]) for p in run["pillars"]}) == 3)

    story("US-26", "E and S keep missing, failed and thin evidence apart",
          "Given Environmental and Social criteria with nothing found, then they carry a named "
          "status with null maturity, exactly like Governance.")
    es_missing = [c for pl in ("ENVIRONMENTAL", "SOCIAL") for c in criteria(run, pl) if c["status"] != "DISCLOSED"]
    verify("E and S have unanswered criteria in the fixture", bool(es_missing))
    verify("none of them is scored as zero", all(c["maturity"] is None for c in es_missing))

    story("US-27", "E and S evidence shows grade and location",
          "Given an Environmental or Social finding, then its evidence carries the source grade, "
          "page and a locator naming the document.")
    es_evidence = [e for pl in ("ENVIRONMENTAL", "SOCIAL") for c in criteria(run, pl) for e in c["evidence"]]
    verify("E and S findings have evidence", bool(es_evidence))
    verify("each has grade, page and locator",
           all(e.get("sourceGrade") and e.get("page") and e.get("locator") for e in es_evidence))

    story("US-28", "The output says a machine interpreted it",
          "Given any run, then the run, every criterion and the PDF state that software formed "
          "the reading and that no analyst reviewed it.")
    verify("the run is marked machine-interpreted and not reviewed",
           run["interpretation"]["method"] == "MACHINE" and run["interpretation"]["humanReviewed"] is False)
    verify("every criterion says MACHINE", all(c["interpretedBy"]["method"] == "MACHINE" for c in criteria(run)))
    verify("every piece of evidence names the engine that actually read it",
           all(e["extractedBy"] == run["interpretation"]["engine"] for c in criteria(run) for e in c["evidence"]))

    story("US-20", "Export a documented PDF report",
          "Given a finished run, when the PDF is requested, then a real PDF comes back covering "
          "every pillar and carrying the machine-interpretation statement.")
    pdf = client.get(f"/api/assessments/{run_id}/report.pdf", headers=H)
    verify("a PDF is returned", pdf.status_code == 200 and pdf.content[:4] == b"%PDF")
    text = " ".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf.content)).pages)
    flat = " ".join(text.split())
    verify("it names all three pillars", all(w in flat for w in ("Governance", "Environmental", "Social")))
    verify("it carries the machine-interpretation statement", "software" in flat.lower())

    story("US-29", "The PDF matches the screen",
          "Given a run, then the band shown for each pillar on screen appears in the PDF.")
    bands = {p["result"]["band"].replace("_", " ").title() for p in run["pillars"]}
    verify("every on-screen band appears in the PDF", all(b.lower() in flat.lower() for b in bands), str(bands))

    story("US-19", "Machine-readable export",
          "Given a run, when it is emailed with JSON, then the outbox holds the PDF and the JSON "
          "result as attachments.")
    story("US-30", "Email the report and see what happened to it",
          "Given no mail server is configured, when the analyst emails the report, then the "
          "message is saved to the outbox and its status says it was saved, not sent.")
    sent = client.post(f"/api/assessments/{run_id}/email", headers=H,
                       json={"to": "investor@example.com", "message": "For review", "includeJson": True})
    verify("the email request is accepted", sent.status_code in (200, 201, 202), sent.text[:200])
    outbox = client.get("/api/outbox", headers=H).json()
    blob = json.dumps(outbox)
    verify("the message is in the outbox", "investor@example.com" in blob)
    mine = [m for m in outbox.get("messages", []) if "investor@example.com" in str(m.get("to"))]
    verify("its status says it was not sent", bool(mine) and mine[0].get("delivery") == "not-sent",
           str(mine[:1])[:300])
    RESULTS[-2]["checks"].append({"check": "PDF and JSON attached", "passed": ".json" in blob and ".pdf" in blob})
    check("US-19: PDF and JSON are attached", ".json" in blob and ".pdf" in blob, blob[:300])

    # ------------------------------------------------- disclosure requests
    story("US-31", "Request a missing disclosure and track it",
          "Given unanswered criteria, when the analyst sends a request, then it is stored with "
          "the company, the items asked for and a status.")
    made = client.post(f"/api/assessments/{run_id}/disclosure-requests", headers=H,
                       json={"contactEmail": "company.secretary@fixture-test.example", "dueDays": 14})
    req = made.json()
    verify("the request is created", made.status_code == 201, made.text[:200])
    verify("it lists the items asked for", bool(req.get("items") or req.get("documents")))
    listed = client.get("/api/disclosure-requests?asxCode=TST", headers=H).json()
    verify("it appears in the request list with a status",
           req["requestId"] in json.dumps(listed) and req.get("status"))

    story("US-32", "The company can respond with a document",
          "Given the secure link from the email, when the company uploads a PDF, then the "
          "request shows it responded.")
    token = req["responseUrl"].rstrip("/").split("/")[-1]
    page = client.get(f"/respond/{token}")
    verify("the response page opens without signing in", page.status_code == 200)
    upload = client.post(f"/respond/{token}", data={"note": "Our board charter"},
                         files=[("files", ("governance-statement.pdf",
                                           (HERE / "fixture-site/docs/corporate-governance-statement-2026.pdf").read_bytes(),
                                           "application/pdf"))])
    verify("the upload is accepted", upload.status_code == 200)
    after = client.get(f"/api/disclosure-requests/{req['requestId']}", headers=H).json()
    verify("the request is marked responded", after.get("status") == "RESPONDED", str(after.get("status")))

    story("US-33", "Company-supplied material is labelled as such",
          "Given a response, when the analyst re-assesses, then the supplied document is in the "
          "source log as provided on request, graded below published documents.")
    re_run = client.post(f"/api/disclosure-requests/{req['requestId']}/reassess", headers=H)
    verify("re-assessment starts", re_run.status_code == 202, re_run.text[:200])
    re_result = wait_for_run(client, re_run.json()["runId"], H)
    supplied = [s for s in re_result["sourceLog"] if s.get("provenance") == "PROVIDED_ON_REQUEST"]
    verify("the supplied document is labelled PROVIDED_ON_REQUEST", bool(supplied))
    verify("text-readable supplied documents are graded C, below published documents",
           all(s.get("sourceGrade") == "C" for s in supplied if s.get("extractionMethod") != "ocr"),
           json.dumps(supplied)[:600])

    story("US-34", "No reply never lowers the score",
          "Given a request that lapses with no reply, then the company's scores are exactly what "
          "the public evidence gave, and the unanswered items read as insufficient information.")
    second = client.post(f"/api/assessments/{again['runId']}/disclosure-requests", headers=H,
                         json={"contactEmail": "company.secretary@fixture-test.example", "dueDays": 1})
    closed = client.post(f"/api/disclosure-requests/{second.json()['requestId']}/close", headers=H,
                         json={"reason": "No reply by the due date"})
    verify("the request can be closed as unanswered", closed.status_code == 200, closed.text[:200])
    stored = client.get(f"/api/assessments/{again['runId']}", headers=H).json()
    verify("practice is unchanged", [p["result"]["practiceScore"]["value"] for p in stored["pillars"]]
           == [p["result"]["practiceScore"]["value"] for p in again["pillars"]])
    verify("transparency is unchanged", [p["result"]["transparencyScore"]["value"] for p in stored["pillars"]]
           == [p["result"]["transparencyScore"]["value"] for p in again["pillars"]])

    # ----------------------------------------------------- administration
    story("US-21", "Review previous assessments and how they were produced",
          "Given earlier runs, then the history lists each with its company and dates, and each "
          "stored run keeps its source log and run steps.")
    history = client.get("/api/assessments?asxCode=TST", headers=H).json()
    rows = history.get("runs", history if isinstance(history, list) else [])
    verify("history lists the runs", len(rows) >= 3, str(history)[:200])
    verify("a stored run keeps its steps and sources",
           bool(stored.get("runLog")) and bool(stored.get("sourceLog")))

    story("US-22", "Assessments are dated",
          "Given the history, then every entry has the date it was requested and completed, "
          "newest first.")
    dates = [r.get("requestedAt") or r.get("completedAt") for r in rows]
    verify("every entry is dated", all(dates))
    verify("newest first", dates == sorted(dates, reverse=True))

    story("US-23", "A company's history is kept",
          "Given a company assessed more than once, then every run is kept and can be opened.")
    verify("all runs for TST can be opened",
           all(client.get(f"/api/assessments/{r['runId']}", headers=H).status_code == 200 for r in rows))

    story("US-37", "Private companies are labelled as private",
          "Given a company added by website with no ASX code, then it is stored and labelled as a "
          "private company, never given an ASX code.")
    added = client.post("/api/companies", headers=H, json={
        "name": "Acme Recycling", "website": "acmerecycling.com.au", "contactEmail": "esg@acme.example"})
    company = added.json().get("company", added.json())
    verify("the company is added", added.status_code == 201, added.text[:200])
    verify("it is marked as not listed", company.get("listed") is False)

if server:
    server.shutdown()

report = os.environ.get("ACCEPTANCE_REPORT")
if report:
    for r in RESULTS:
        r["passed"] = all(c["passed"] for c in r["checks"]) and bool(r["checks"])
    Path(report).write_text(json.dumps({"stories": RESULTS}, indent=2))
    print(f"\n  wrote {report}")

done()
