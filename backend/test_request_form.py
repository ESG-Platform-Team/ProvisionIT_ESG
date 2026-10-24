#!/usr/bin/env python3
"""The request form: choose ESG documents, write a note, preview the exact email,
send it, and the company sees the same checklist on its response page."""

import os
import tempfile
from pathlib import Path

from testkit import check, done, section

TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'platform.db'}"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-signing"
os.environ["MAIL_DIR"] = str(TMP / "mail")
os.environ["RESPONSE_DIR"] = str(TMP / "responses")
for k in ("SMTP_HOST", "AUTH_REQUIRED", "SMTP_REPLY_TO"):
    os.environ.pop(k, None)

from fastapi.testclient import TestClient  # noqa: E402

from app import companies, db, store  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
tok = client.post("/api/auth/signup", json={"name": "Agam Johal", "email": "agam@example.com",
                                             "password": "long enough pw"}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}
acme = companies.add_private("Acme Recycling", "acmerecycling.com.au", "esg@acme.example")

section("CATALOGUE")
cat = client.get("/api/disclosure-requests/catalogue", headers=H).json()["documents"]
check("documents cover all three pillars",
      {d["pillar"] for d in cat} == {"GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"})
check("the catalogue includes the core ESG documents",
      {"climate_disclosure", "modern_slavery_statement", "emissions_inventory"} <= {d["key"] for d in cat})

form = {"companyCode": acme["asxCode"], "contactName": "Jo Smith",
        "documents": ["climate_disclosure", "emissions_inventory", "modern_slavery_statement",
                      "board_charter"],
        "custom": ["Your 2025 solar installation figures"],
        "message": "Thanks for speaking with us last week.", "dueDays": 14}

section("PREVIEW")
pv = client.post("/api/disclosure-requests/preview", json=form, headers=H)
body = pv.json()
text = body.get("text", "")
check("the preview works without sending", pv.status_code == 200 and not store.list_requests())
check("it greets the contact by name", text.startswith("Dear Jo Smith,"))
check("it includes the personal note", "Thanks for speaking with us last week." in text)
check("documents are grouped under their pillar",
      text.index("Governance") < text.index("Board charter") < text.index("Environmental")
      < text.index("Climate-related financial disclosure") < text.index("Social"))
check("written-in items appear", "Also requested" in text and "solar installation" in text)
check("it says what happens with no reply", "insufficient information" in text)
check("it is signed by the analyst", "Agam Johal" in text and "agam@example.com" in text)
check("the contact email defaults to the company's", body["to"] == "esg@acme.example")
check("the subject names the company and due date",
      "Acme Recycling (private company)" in body["subject"] and "by " in body["subject"])
check("the item count is right", body["itemCount"] == 5)
empty = client.post("/api/disclosure-requests/preview",
                    json={"companyCode": acme["asxCode"]}, headers=H)
check("a preview with nothing chosen says so", empty.status_code == 400 and "at least one" in empty.text)
bad = client.post("/api/disclosure-requests/preview",
                  json=dict(form, documents=["made_up"]), headers=H)
check("an unknown document type is refused", bad.status_code == 400)

section("SEND")
sent = client.post("/api/disclosure-requests", json=form, headers=H)
out = sent.json()
check("the request is sent without needing an assessment",
      sent.status_code == 201 and out["status"] == "SENT" and out["runId"] is None)
check("it lists the four documents", len(out["documents"]) == 4)
again = client.post("/api/disclosure-requests", json=form, headers=H)
check("a second open request to the same company is refused", again.status_code == 409)
with db.session() as s:
    kinds = sorted(r.kind for r in s.query(db.RequestItem).all())
check("each item is stored with its kind",
      kinds == ["custom", "document", "document", "document", "document"])
page = client.get(out["responseUrl"].replace("http://localhost:8080", "")).text
check("the company's page shows the same checklist",
      "Climate-related financial disclosure" in page and "solar installation" in page
      and "Environmental" in page)
eml = sorted((TMP / "mail").glob("*disclosure-request*.eml"))[-1].read_text()
check("the sent email has an HTML version with an upload button",
      "text/html" in eml and "Upload documents or decline" in eml)

section("SEEING WHAT THE COMPANY SENT")
token_path = out["responseUrl"].replace("http://localhost:8080", "")
up = client.post(token_path, files=[("files", ("msa-2025.pdf", b"%PDF-1.4 modern slavery", "application/pdf"))],
                 data={"note": "Climate disclosure is in our annual report, page 12.", "name": "Jo Smith",
                       "email": "jo@acme.example"})
check("the company can upload through its link", up.status_code == 200)
detail = client.get(f"/api/disclosure-requests/{out['requestId']}", headers=H).json()
docs = detail["response"]["documents"]
check("the analyst sees the documents and who sent them",
      len(docs) == 2 and detail["response"]["respondentName"] == "Jo Smith")
check("server file paths are never exposed", all("path" not in d for d in docs))
pdf = client.get(f"/api/disclosure-requests/{out['requestId']}/documents/0", headers=H)
check("a supplied document opens", pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
      and pdf.headers["content-type"] == "application/pdf")
note = client.get(f"/api/disclosure-requests/{out['requestId']}/documents/1", headers=H)
check("the company's note opens too", b"annual report, page 12" in note.content)
check("documents need a signed-in user",
      client.get(f"/api/disclosure-requests/{out['requestId']}/documents/0").status_code == 401)
check("a document number that does not exist is a 404",
      client.get(f"/api/disclosure-requests/{out['requestId']}/documents/9", headers=H).status_code == 404)

section("WITH AN ASSESSMENT")
from testfixtures import fake_run  # noqa: E402

run = fake_run()
store.save_run(run)
pv2 = client.post("/api/disclosure-requests/preview", headers=H, json={
    "companyCode": "TST", "documents": ["wgea_report"], "runId": run["runId"], "includeGaps": True})
t2 = pv2.json()["text"]
check("the criteria the assessment could not answer can be added",
      "From our assessment" in t2 and "G1.2" in t2 and "Workplace Gender Equality" in t2)

done()
