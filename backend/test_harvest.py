#!/usr/bin/env python3
"""Crawler rules that can be checked without a network."""

import asyncio
import socket

from testkit import check, done, section

from app.harvest import Harvester, _classify, latest_only, new_client


def closed_port_url() -> str:
    """A local address nothing listens on, so a fetch fails at once, offline."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/"

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

section("A SITE THAT CANNOT BE REACHED (ESG-58, TC07)")


async def _discover_unreachable():
    hv = Harvester(delay=0)
    async with new_client() as client:
        found = await hv.discover(client, closed_port_url())
    return hv, found

hv, found = asyncio.run(_discover_unreachable())
check("discovery finds nothing", found == [])
check("the failed home page fetch is kept", hv.home_task is not None)
check("it is recorded as NOT_FOUND", hv.home_task and hv.home_task.status == "NOT_FOUND")
check("the error type is recorded", hv.home_task and hv.home_task.note == "ConnectError",
      hv.home_task and hv.home_task.note)

done()
