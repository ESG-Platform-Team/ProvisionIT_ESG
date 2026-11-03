#!/usr/bin/env python3
"""Two undated editions of one report: the PDF's own metadata date picks the
newest, and only that one is read (ESG-56). Offline: a small site with two
annual reports is served from a temporary folder on a local port."""

import asyncio
import functools
import http.server
import io
import tempfile
import threading
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from testkit import check, done, section

from app import harvest, pipeline


def make_pdf(lines: list[str], created: str | None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for line in lines:
        c.drawString(60, y, line)
        y -= 18
    c.showPage()
    c.save()
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(buf.getvalue())).pages:
        writer.add_page(page)
    # Replace whatever reportlab wrote with only the date under test.
    writer.metadata = None
    writer.add_metadata({"/Producer": "test"} | ({"/CreationDate": created} if created else {}))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


FILLER = ["This annual report describes the company and its year in some detail.",
          "It is long enough to count as a text layer rather than a scanned image.",
          "The directors present their report for the financial year."]
OLD = make_pdf(FILLER + ["The company has adopted a whistleblower policy.",
                         "Material incidents are reported to the audit committee."],
               "D:20230915090000+10'00'")
NEW = make_pdf(FILLER + ["The board charter sets out the respective roles and",
                         "responsibilities of the board and management."],
               "D:20260915090000+10'00'")
UNDATED = make_pdf(FILLER, None)

section("PDF METADATA DATES")
check("a PDF's creation date is read", harvest.pdf_date(NEW) is not None
      and harvest.pdf_date(NEW).year == 2026)
check("a page that is not a PDF has no date", harvest.pdf_date(b"<html></html>") is None)
check("a PDF with no date in its metadata has none", harvest.pdf_date(UNDATED) is None)


def cand(title, url, source_type="annual_report"):
    return {"title": title, "url": url, "source_type": source_type, "is_pdf": True}


section("CHOOSING BETWEEN UNDATED EDITIONS")
pair = [(cand("Annual report", "https://x/ar-a.pdf"), OLD),
        (cand("Annual report", "https://x/ar-b.pdf"), NEW)]
check("the older undated edition is set aside for the newer",
      harvest.superseded_editions(pair) == {0: 1})
check("nothing is set aside when one edition has no metadata date to compare",
      harvest.superseded_editions([pair[1], (pair[0][0], UNDATED)]) == {})
check("charters are not editions, so two of them are both kept",
      harvest.superseded_editions([(cand("Charter", "https://x/a.pdf", "board_charter"), OLD),
                                   (cand("Charter", "https://x/b.pdf", "board_charter"), NEW)]) == {})
check("a dated title is left to latest_only",
      harvest.superseded_editions([(cand("Annual report 2023", "https://x/a.pdf"), OLD),
                                   pair[1]]) == {})

section("A RUN ONLY READS THE NEWEST UNDATED EDITION")
site = Path(tempfile.mkdtemp())
(site / "docs").mkdir()
(site / "docs" / "annual-report-a.pdf").write_bytes(OLD)
(site / "docs" / "annual-report-b.pdf").write_bytes(NEW)
(site / "index.html").write_text(
    '<html><body><a href="/docs/annual-report-a.pdf">Annual report</a>'
    '<a href="/docs/annual-report-b.pdf">Annual report</a></body></html>')


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(
    ("127.0.0.1", 0), functools.partial(_Quiet, directory=str(site)))
threading.Thread(target=server.serve_forever, daemon=True).start()
company = {"asxCode": "PVT3", "name": "Two Reports Pty Ltd", "listed": False,
           "website": f"http://127.0.0.1:{server.server_address[1]}/"}
out = asyncio.run(pipeline.run_assessment(
    company, pipeline.RunState("run_editions", company), use_llm=False))
server.shutdown()

log = {d["url"].rsplit("/", 1)[-1]: d for d in out["sourceLog"]}
old, new = log.get("annual-report-a.pdf"), log.get("annual-report-b.pdf")
check("both editions are in the source log as retrieved",
      old and new and old["outcome"] == new["outcome"] == "RETRIEVED", list(log))
check("the older edition says it was set aside for the newer",
      old and old.get("supersededBy") == new["sourceDocumentId"]
      and "Older edition" in old["note"], old)
check("the older edition does not count toward confidence", old and old["sourceGrade"] is None)
check("the newer edition is read as usual",
      new and new["sourceGrade"] == "A" and not new.get("supersededBy"))
rows = {r["criterionCode"]: r for p in out["principles"] for r in p["criteria"]}
cited = {ev["sourceDocumentId"] for r in rows.values() for ev in r["evidence"]}
check("no evidence is quoted from the older edition", old and old["sourceDocumentId"] not in cited,
      cited)
check("evidence from the newer edition is used", new and new["sourceDocumentId"] in cited, cited)
check("a policy only the older edition mentions is not credited",
      rows["G3.3"]["status"] != "DISCLOSED", rows["G3.3"]["status"])

done()
