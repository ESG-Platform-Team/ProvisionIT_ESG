#!/usr/bin/env python3
"""The multi-pillar run payload and the machine interpretation statement."""

from testfixtures import fake_run
from testkit import check, done, section

from app import pipeline

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

done()
