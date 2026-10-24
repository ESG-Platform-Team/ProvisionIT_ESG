#!/usr/bin/env python3
"""Demo speed: no politeness pause for our own fixture, and replay mode answers
from recorded model output without calling the API."""

import asyncio
import os
import tempfile
from pathlib import Path

from testkit import check, done, section

from app import harvest, llm, pillars

section("POLITENESS DELAY ONLY FOR OTHER PEOPLE'S SERVERS")
check("the local fixture company is recognised as ours",
      harvest.is_local("http://localhost:8123/docs/annual-report-2026.pdf"))
check("127.0.0.1 counts as local", harvest.is_local("http://127.0.0.1:8123/"))
check("a real company website is not local",
      not harvest.is_local("https://www.bendigobank.com.au/governance"))
check("a lookalike host is not local", not harvest.is_local("https://localhost.evil.com/"))


async def _waits(url, delay=0.2):
    h = harvest.Harvester(delay=delay)
    loop = asyncio.get_running_loop()
    await h._polite_wait(url)
    t0 = loop.time()
    await h._polite_wait(url)
    return loop.time() - t0

check("no pause between two local fetches",
      asyncio.run(_waits("http://localhost:8123/a.pdf")) < 0.05)
check("a pause between two fetches from a real host",
      asyncio.run(_waits("https://example.com/a.pdf")) >= 0.15)

section("REPLAY MODE")
principle = pillars.get("GOVERNANCE")["principles"][0]
passages = [("Annual Report 2026", 4, "The board charter sets out roles and responsibilities.")]
recorded = [{"criterionCode": principle["criteria"][0]["criterionCode"], "found": True}]

with tempfile.TemporaryDirectory() as tmp:
    old_dir, old_env = llm.CACHE_DIR, os.environ.get("LLM_REPLAY")
    llm.CACHE_DIR = Path(tmp)
    os.environ["LLM_REPLAY"] = "1"
    try:
        client = llm.GeminiClient(api_key="")
        check("replay mode counts as configured without an API key", client.configured)

        def run():
            return asyncio.run(client.extract_principle(None, principle, passages, "G-test"))

        try:
            run()
            missed = False
        except RuntimeError:
            missed = True
        check("an unrecorded prompt raises, so the pipeline falls back to keywords", missed)

        prompt = llm._build_prompt(principle, passages, "ASX Corporate Governance Council",
                                   "Principle")
        llm._cache_write(llm._cache_key(client.model, "G-test", principle["number"], prompt),
                         recorded)
        check("a recorded prompt returns the recorded findings", run() == recorded)
        check("and it never called the API", client.calls_made == 0 and client.cache_hits == 1)
    finally:
        llm.CACHE_DIR = old_dir
        if old_env is None:
            os.environ.pop("LLM_REPLAY", None)
        else:
            os.environ["LLM_REPLAY"] = old_env

done()
