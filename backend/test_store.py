#!/usr/bin/env python3
"""The relational database: runs, pillar results, sources, requests and their
items land in their own tables with working foreign keys."""

import os
import tempfile
from pathlib import Path

from testkit import check, done, raises, section

TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'platform.db'}"
os.environ["MAIL_DIR"] = str(TMP / "mail")
os.environ.pop("SMTP_HOST", None)

from sqlalchemy import func, inspect, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from testfixtures import fake_run  # noqa: E402

from app import db, disclosure, store  # noqa: E402

section("SCHEMA")
tables = set(inspect(db.engine()).get_table_names())
expected = {"users", "revoked_tokens", "companies", "assessment_runs", "pillar_results",
            "source_documents", "disclosure_requests", "request_items", "request_documents",
            "email_log"}
check("every table exists", expected <= tables, str(expected - tables))
fks = {fk["referred_table"] for fk in inspect(db.engine()).get_foreign_keys("assessment_runs")}
check("runs reference companies and users", {"companies", "users"} <= fks)

section("RUNS")
store.save_user({"userId": "usr_test", "name": "Ann", "email": "ann@example.com",
                 "passwordHash": "x", "createdAt": "2026-10-12T00:00:00Z"})
run = fake_run()
run["requestedBy"] = {"name": "Ann", "email": "ann@example.com"}
store.save_run(run)
with db.session() as s:
    n_pillars = s.scalar(select(func.count()).select_from(db.PillarResult))
    n_sources = s.scalar(select(func.count()).select_from(db.SourceDocument))
    row = s.get(db.AssessmentRun, run["runId"])
    check("one row per pillar result", n_pillars == 3)
    check("one row per source document", n_sources == len(run["sourceLog"]))
    check("the run is linked to the user who ran it", row.requested_by == "usr_test")
    check("the company row was created", row.company.code == "TST")
check("the issued payload comes back exactly", store.get_run(run["runId"]) == run)
hist = store.list_runs()
check("history is built from the relational columns",
      hist[0]["requestedBy"] == "Ann" and len(hist[0]["pillars"]) == 3)
store.save_run(run)
with db.session() as s:
    check("saving a run again replaces its child rows, it does not duplicate them",
          s.scalar(select(func.count()).select_from(db.PillarResult)) == 3)

section("REQUESTS")
req = disclosure.create(run, "cosec@test.example", requested_by="Ann")
req["requestedByEmail"] = "ann@example.com"
store.save_request(req)
with db.session() as s:
    items = s.scalar(select(func.count()).select_from(db.RequestItem))
    check("each requested criterion is its own row", items == len(req["items"]))
disclosure.close(req)
store.save_request(req)
with db.session() as s:
    check("updating a request keeps one row per item",
          s.scalar(select(func.count()).select_from(db.RequestItem)) == len(req["items"]))
    check("the status column follows the request",
          s.get(db.DisclosureRequest, req["requestId"]).status == "NO_RESPONSE")
check("a request is found by its token", store.get_request_by_token(req["token"])["requestId"]
      == req["requestId"])
check("requests list by company", len(store.list_requests("TST")) == 1)


def orphan():
    with db.session() as s, s.begin():
        s.add(db.RequestItem(request_id="req_missing", criterion_code="G1.1", pillar="GOVERNANCE",
                             status_at_request="EVIDENCE_GAP"))


check("foreign keys are enforced", raises(orphan, IntegrityError))

section("COMPANIES AND EMAIL LOG")
store.save_company({"asxCode": "PRIV1", "name": "Private Co", "website": "https://private.example",
                    "listed": False, "contactEmail": "ceo@private.example"}, created_by="usr_test")
check("a private company can be stored", store.get_company("PRIV1")["listed"] is False)
check("listed and private companies can be filtered",
      [c["asxCode"] for c in store.list_companies(listed=False)] == ["PRIV1"])
store.log_email("report", {"to": "a@x.com", "subject": "S", "delivered": False, "record": "r.eml"},
                "usr_test", run_id=run["runId"])
check("every email is logged with who sent it", store.email_log()[0]["sentBy"] == "usr_test")

done()
