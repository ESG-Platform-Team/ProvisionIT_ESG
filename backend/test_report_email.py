#!/usr/bin/env python3
"""The PDF report and the outbound mailer. SMTP is never configured here, so
nothing leaves the machine; every message lands in a temporary outbox."""

import asyncio
import os
import tempfile
from pathlib import Path

from testfixtures import fake_run
from testkit import check, done, raises, section

TMP = Path(tempfile.mkdtemp())
os.environ["MAIL_DIR"] = str(TMP / "mail")
os.environ.pop("SMTP_HOST", None)

from app import mailer, report  # noqa: E402

mailer.MAIL_DIR = TMP / "mail"
run = fake_run()

section("PDF REPORT")
pdf = report.render(run)
check("the report is a PDF", pdf[:4] == b"%PDF")
check("the report is not trivially small", len(pdf) > 10000, f"{len(pdf)} bytes")

section("EMAIL, SAFE BY DEFAULT")
check("recipients are split and de-duplicated",
      mailer.clean_recipients("a@x.com; A@x.com, b@y.org") == ["a@x.com", "b@y.org"])
check("a bad address is refused, not dropped",
      raises(lambda: mailer.clean_recipients("a@x.com, nope"), ValueError))
check("more than ten recipients is refused",
      raises(lambda: mailer.clean_recipients([f"u{i}@x.com" for i in range(11)]), ValueError))
msg = mailer.build(["a@x.com"], "Report", "body", attachments=[("r.pdf", pdf, "application/pdf")])
sent = asyncio.run(mailer.send(msg, "report"))
check("without SMTP nothing is delivered", sent["delivered"] is False and sent["mode"] == "outbox")
check("but a copy is always kept", Path(sent["record"]).exists())
check("the kept copy carries the PDF", b"r.pdf" in Path(sent["record"]).read_bytes())

section("REPORT EMAIL LAYOUT")
from app.main import _report_email_html  # noqa: E402

html = _report_email_html(run, "Hello <Mick>", True)
check("the summary is a table with one row per pillar", html.count("<tr>") == len(run["pillars"]))
check("the machine interpretation statement is in the email", "formed by software" in html)
check("the personal message is escaped", "Hello &lt;Mick&gt;" in html)

done()
