#!/usr/bin/env python3
"""Disclosure requests: asking a company for what public sources lacked, and
what happens when it answers, declines or stays silent."""

import asyncio
import datetime as dt
import os
import tempfile
from pathlib import Path

from testfixtures import fake_run
from testkit import check, done, raises, section

TMP = Path(tempfile.mkdtemp())
os.environ["MAIL_DIR"] = str(TMP / "mail")
os.environ["RESPONSE_DIR"] = str(TMP / "responses")
os.environ.pop("SMTP_HOST", None)

from app import disclosure, mailer, pipeline, report  # noqa: E402

mailer.MAIL_DIR = TMP / "mail"
disclosure.RESPONSE_DIR = TMP / "responses"
run = fake_run()

section("DISCLOSURE REQUESTS")
req = disclosure.create(run, "cosec@test.example", requested_by="Analyst")
check("a request lists what public sources did not answer",
      req["items"] and all(i["status"] in disclosure.REQUESTABLE for i in req["items"]))
check("a bad contact address is refused",
      raises(lambda: disclosure.create(run, "not-an-email"), disclosure.RequestError))
check("a second open request is refused",
      raises(lambda: disclosure.create(run, "cosec@test.example", existing=[req]),
             disclosure.RequestError))
req = asyncio.run(disclosure.send(req, "http://localhost:8080"))
check("an unsent request is recorded as not delivered", req["delivery"]["delivered"] is False)
body = Path(req["delivery"]["record"]).read_text()
check("the email explains non-response", "insufficient" in body and "information" in body)
check("the email offers an opt-out", "no further requests" in body)
check("the summary never carries the token", "token" not in disclosure.summary(req))

past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
req["dueAt"] = disclosure._iso(past)
check("an undelivered request does not lapse", disclosure.refresh(dict(req))["status"] == "SENT")
lapsed = disclosure.refresh(dict(req, delivery={"delivered": True}))
check("a delivered request lapses to NO_RESPONSE after the due date",
      lapsed["status"] == "NO_RESPONSE")

check("an unsupported file type is refused",
      raises(lambda: disclosure.record_response(dict(req), [("x.exe", b"MZ")]),
             disclosure.RequestError))
answered = disclosure.record_response(dict(req), [("msa.pdf", b"%PDF-1.4 test")], note="See RAP")
check("a response closes the request", answered["status"] == "RESPONDED")
check("response documents are marked provided on request",
      all("provided on request" in d["title"] for d in disclosure.response_documents([answered])))
check("an answered request cannot be answered twice",
      raises(lambda: disclosure.record_response(answered, [], note="again"),
             disclosure.RequestError))

declined = disclosure.decline(dict(req), reason="confidential", opt_out=True)
check("a decline with opt-out is honoured",
      raises(lambda: disclosure.create(run, "cosec@test.example", existing=[declined]),
             disclosure.RequestError))

section("NON-RESPONSE IS INSUFFICIENT INFORMATION, NEVER A ZERO")
closed = disclosure.close(dict(req, dueAt=disclosure._iso(past + dt.timedelta(days=30))))
gap_code = next(i["criterionCode"] for i in req["items"] if i["status"] == "EVIDENCE_GAP")
run2 = fake_run([disclosure.summary(closed)])
row2 = next(r for p in run2["pillars"] for pr in p["principles"] for r in pr["criteria"]
            if r["criterionCode"] == gap_code)
check("an unanswered request does not change the status", row2["status"] == "EVIDENCE_GAP")
check("an unanswered request does not create a maturity", row2["maturity"] is None)
check("the row says it is insufficient information",
      "insufficient information" in row2["disclosureRequest"]["note"])
check("an early close is described as such",
      "closed without a response" in row2["disclosureRequest"]["note"])
due_note = pipeline._request_note(dict(closed, closedAt=closed["dueAt"]), "NOT_DISCLOSED")
check("a lapsed request on a public silence stays not disclosed",
      "no response by the due date" in due_note and "remains not disclosed" in due_note)
check("a PDF renders with request notes in it", report.render(run2)[:4] == b"%PDF")

done()
