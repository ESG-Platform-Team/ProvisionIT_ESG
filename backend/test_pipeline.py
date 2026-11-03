#!/usr/bin/env python3
"""The multi-pillar run payload and the machine interpretation statement."""

import asyncio
import socket

from testfixtures import fake_run
from testkit import check, done, section

from app import pipeline, scoring

section("MACHINE INTERPRETATION DISCLAIMER")
llm_stmt = pipeline.interpretation_statement("LLM", "gemini-3.6-flash")
kw_stmt = pipeline.interpretation_statement("KEYWORD", None)
check("the statement names software, not a person", "software, not by a person" in llm_stmt)
check("the statement names the model used", "gemini-3.6-flash" in llm_stmt)
check("keyword runs say keyword matching", "Keyword-matching software" in kw_stmt)
check("no run claims a human review", "No analyst has reviewed" in kw_stmt)

section("RUN PAYLOAD")
run = fake_run()
check("every row says a machine interpreted it",
      all(r["interpretedBy"]["method"] == "MACHINE"
          for p in run["pillars"] for pr in p["principles"] for r in pr["criteria"]))
check("the run is marked not human reviewed", run["interpretation"]["humanReviewed"] is False)
check("all three pillars are present", [p["pillar"] for p in run["pillars"]]
      == ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"])
check("the top level stays governance for v0.1 clients",
      run["result"] is run["pillars"][0]["result"])

section("A SITE THAT CANNOT BE REACHED (ESG-58, TC07)")
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    dead = f"http://127.0.0.1:{sock.getsockname()[1]}/"
company = {"asxCode": "PVT1", "name": "Unreachable Pty Ltd", "website": dead, "listed": False}
state = pipeline.RunState("run_unreachable", company)
out = asyncio.run(pipeline.run_assessment(company, state, use_llm=False))
log = out["sourceLog"]
check("the run completes", out["status"] == "COMPLETE")
check("it still declines to rate", out["result"]["band"] == "INSUFFICIENT_EVIDENCE")
check("the source log has a row for the home page", len(log) == 1, f"got {len(log)} rows")
check("the row is NOT_FOUND with the error type",
      log and log[0]["outcome"] == "NOT_FOUND" and log[0]["note"] == "ConnectError"
      and log[0].get("homePage") is True, log[:1])
check("the counts show one source attempted",
      out["result"]["counts"]["sourcesAttempted"] == 1
      and out["result"]["counts"]["sourcesRetrieved"] == 0)
reason = out["result"]["declineReason"] or ""
check("the decline says the website could not be reached",
      reason.startswith("The company website could not be reached (ConnectError)"), reason)
check("the decline still gives the coverage figure", "in-scope criteria could be reached" in reason)
home_row = dict(log[0]) if log else {}
other = scoring.score_run({}, [home_row, {"outcome": "RETRIEVED", "sourceGrade": "B"}], set())
check("a reachable source elsewhere keeps the usual reason",
      "could not be reached (" not in (other["result"]["declineReason"] or ""))

done()
