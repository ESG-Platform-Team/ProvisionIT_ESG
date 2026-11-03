#!/usr/bin/env python3
"""A poller in the same process sees every stage of a run, even a keyword run
that reads and scores in milliseconds (ESG-61, TC34). Offline: the company
website is a local port nothing listens on."""

import asyncio
import socket

from testkit import check, done, section

from app import pipeline


def dead_site() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}/"


async def run_and_poll(pillar_keys):
    company = {"asxCode": "PVT2", "name": "Stage Test Pty Ltd", "website": dead_site(),
               "listed": False}
    state = pipeline.RunState("run_stages", company, pillar_keys)
    observed: list[str] = []

    async def poll():
        # Polls as often as the event loop allows, like the API handler would
        # if it were asked between every step.
        while state.status != "COMPLETE":
            if not observed or observed[-1] != state.stage:
                observed.append(state.stage)
            await asyncio.sleep(0)

    poller = asyncio.create_task(poll())
    payload = await pipeline.run_assessment(company, state, use_llm=False,
                                            pillar_keys=pillar_keys)
    await poller
    return state, observed, payload


section("STAGES A POLLER CAN SEE (ESG-61, TC34)")
state, observed, payload = asyncio.run(run_and_poll(["GOVERNANCE"]))
check("the run completes", payload["status"] == "COMPLETE")
check("the run is a keyword run", payload["interpretation"]["engine"] == "KEYWORD")
check("the poller sees HARVEST", "HARVEST" in observed, observed)
check("the poller sees EXTRACT", "EXTRACT" in observed, observed)
check("the poller sees SCORE", "SCORE" in observed, observed)
check("the poller sees AGGREGATE", "AGGREGATE" in observed, observed)
check("stages are seen in order",
      [s for s in observed if s in ("HARVEST", "EXTRACT", "SCORE", "AGGREGATE")]
      == ["HARVEST", "EXTRACT", "SCORE", "AGGREGATE"], observed)
check("the run records the stages it went through",
      state.stages_seen == ["QUEUED", "HARVEST", "EXTRACT", "SCORE", "AGGREGATE", "COMPLETE"],
      state.stages_seen)

state3, observed3, _ = asyncio.run(run_and_poll(["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"]))
check("with three pillars, each is read before it is scored",
      state3.stages_seen.count("EXTRACT") == 3 and state3.stages_seen.count("SCORE") == 3,
      state3.stages_seen)

done()
