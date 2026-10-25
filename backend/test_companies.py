#!/usr/bin/env python3
"""Private companies: added by website, stored, found, assessed and labelled
correctly in emails and reports."""

import os
import tempfile
from pathlib import Path

from testkit import check, done, raises, section

TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'platform.db'}"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-signing"
os.environ["MAIL_DIR"] = str(TMP / "mail")
os.environ.pop("SMTP_HOST", None)
os.environ.pop("AUTH_REQUIRED", None)

from fastapi.testclient import TestClient  # noqa: E402

from app import companies, disclosure, report  # noqa: E402
from app.main import app  # noqa: E402

section("ADDING A PRIVATE COMPANY")
acme = companies.add_private("Acme Recycling", "acmerecycling.com.au", "ceo@acmerecycling.com.au")
check("a code is made from the website", acme["asxCode"] == "ACMERECY")
check("it is marked private", acme["listed"] is False and acme["tier"] == "Private")
check("the website gets a scheme", acme["website"] == "https://acmerecycling.com.au")
again = companies.add_private("Acme", "https://www.acmerecycling.com.au/", "")
check("adding the same website again returns the same company", again["asxCode"] == acme["asxCode"])
check("a bad website is refused",
      raises(lambda: companies.add_private("X", "not a site", ""), companies.CompanyError))
check("a bad contact email is refused",
      raises(lambda: companies.add_private("Y", "y-co.com", "nope"), companies.CompanyError))
clash = companies.add_private("Acme Two", "acmerecycling.net", "")
check("codes never collide", clash["asxCode"] != acme["asxCode"])

section("FINDING IT")
check("found by name", companies.find("acme recycling")[0]["asxCode"] == acme["asxCode"])
check("found by website", companies.find("acmerecycling.com.au")[0]["asxCode"] == acme["asxCode"])
check("found by code", companies.get(acme["asxCode"])["name"] == "Acme Recycling")
check("listed companies are still there", companies.get("BEN")["listed"] is True)
check("all companies lists seeds and added ones together",
      {"BEN", acme["asxCode"]} <= {c["asxCode"] for c in companies.all_companies()})

section("LABELS")
check("a listed company is labelled with its ASX code",
      companies.label(companies.get("BEN")) == "Bendigo and Adelaide Bank (ASX: BEN)")
check("a private company is not given an ASX code",
      companies.label(acme) == "Acme Recycling (private company)")

from testfixtures import fake_run  # noqa: E402

run = fake_run()
run["company"] = acme
req = disclosure.create(run, acme["contactEmail"])
msg = disclosure.compose(req, "http://localhost:8080")
body = msg.get_body(("plain",)).get_content()
check("the request email names it as a private company",
      "Acme Recycling (private company)" in body and "ASX:" not in body)
check("the report renders for a private company", report.render(run)[:4] == b"%PDF")

section("THE API")
client = TestClient(app)
check("adding a company needs a signed-in user",
      client.post("/api/companies", json={"website": "z.com"}).status_code == 401)
tok = client.post("/api/auth/signup", json={"name": "Ann", "email": "ann@x.com",
                                             "password": "long enough pw"}).json()["token"]
h = {"Authorization": f"Bearer {tok}"}
r = client.post("/api/companies", json={"name": "Green Freight", "website": "greenfreight.com.au",
                                        "contactEmail": "ops@greenfreight.com.au"}, headers=h)
check("a signed-in analyst can add a private company", r.status_code == 201 and r.json()["listed"] is False)
bad = client.post("/api/companies", json={"website": "nonsense"}, headers=h)
check("a bad website comes back as a plain 400", bad.status_code == 400 and "website" in bad.text)
everyone = client.get("/api/companies?all=true", headers=h).json()["matches"]
check("the company list includes it", any(c["name"] == "Green Freight" for c in everyone))

done()
