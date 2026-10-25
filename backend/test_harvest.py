#!/usr/bin/env python3
"""Crawler rules that can be checked without a network."""

from testkit import check, done, section

from app.harvest import _classify, latest_only

section("ESG DOCUMENT TYPES")
check("a modern slavery statement is recognised",
      _classify("2025 modern slavery statement /msa.pdf") == "modern_slavery_statement")
check("a climate statement is recognised",
      _classify("climate-related financial disclosures tcfd.pdf") == "climate_statement")
check("a privacy policy is recognised", _classify("privacy policy /privacy") == "privacy_policy")

section("ONLY THE NEWEST EDITION IS FETCHED")
archive = [{"title": f"{y} Modern Slavery Statement", "url": f"https://x/msa-{y}.pdf",
            "source_type": "modern_slavery_statement"} for y in (2021, 2022, 2025)]
archive.append({"title": "Board Charter", "url": "https://x/board-charter.pdf",
                "source_type": "board_charter"})
kept = latest_only(archive)
check("older editions of a report are dropped",
      [d["title"] for d in kept if "Slavery" in d["title"]] == ["2025 Modern Slavery Statement"])
check("undated documents are all kept", any(d["title"] == "Board Charter" for d in kept))

done()
