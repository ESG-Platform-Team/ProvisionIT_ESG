"""A small, fully offline run payload with all three pillars, built with the
real scoring engine and the real pipeline assembly. Used by the report, email
and disclosure tests so they exercise the same shape the API returns."""

from testkit import docs

from app import pillars, pipeline, scoring


def fake_run(disclosure_requests=None):
    state = pipeline.RunState("run_test", {"asxCode": "TST", "name": "Test Holdings"},
                              list(pillars.ORDER))
    results = []
    for key in pillars.ORDER:
        spec = pillars.get(key)
        first = spec["principles"][0]["criteria"][0]["criterionCode"]
        found = {first: {"criterionCode": first, "found": True, "explainedDeparture": False,
                         "maturitySignal": "STATED", "rationale": "stated",
                         "excerpt": "The board charter sets out roles", "page": 2,
                         "confidence": 0.5}}
        sc = scoring.score_run(found, docs("A"), set(), spec["principles"])
        for p in sc["principles"]:
            for row in p["criteria"]:
                pipeline._finish_row(row, {"sourceGrade": "A", "title": "Annual report"},
                                     "KEYWORD", None, disclosure_requests or [])
        results.append({"pillar": spec["pillar"], "label": spec["label"],
                        "matrixVersion": spec["matrixVersion"],
                        "frameworkEdition": spec["frameworkEdition"],
                        "frameworkName": spec["frameworkName"], "unitName": spec["unitName"],
                        "draft": spec["draft"], "result": sc["result"],
                        "principles": sc["principles"]})
    log = [{"title": "Annual report", "url": "https://example.com/ar.pdf",
            "outcome": "RETRIEVED", "sourceGrade": "A", "provenance": "PUBLIC"}]
    return pipeline._assemble(state.company, state, results, log, "KEYWORD", None,
                              disclosure_requests or [])
