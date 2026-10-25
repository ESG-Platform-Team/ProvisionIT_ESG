#!/usr/bin/env python3
"""Environmental and Social matrices, the pillar registry, and the new source
grades. The scoring engine is shared, so these check it treats every pillar the
same way."""

from testkit import check, docs, done, raises, section

from app import pillars, scoring

section("THREE PILLARS")
codes, prefixes_ok = [], True
for key in pillars.ORDER:
    spec = pillars.get(key)
    for pr in spec["principles"]:
        for c in pr["criteria"]:
            codes.append(c["criterionCode"])
            prefixes_ok &= c["criterionCode"][0] == key[0]
            check(f"{c['criterionCode']} has keywords", bool(c.get("keywords")))
check("criterion codes are unique across all three matrices", len(codes) == len(set(codes)))
check("each code carries its pillar letter", prefixes_ok)
check("'ALL' expands to every pillar in display order", pillars.normalise("all") == pillars.ORDER)
check("an unknown pillar is refused", raises(lambda: pillars.normalise(["FINANCE"]), KeyError))
check("environmental and social are marked draft",
      pillars.get("ENVIRONMENTAL")["draft"] and pillars.get("SOCIAL")["draft"])
check("governance is not marked draft", not pillars.get("GOVERNANCE")["draft"])


def full_findings(principles):
    return {c["criterionCode"]: {"criterionCode": c["criterionCode"], "found": True,
                                 "explainedDeparture": False, "maturitySignal": "EMBEDDED",
                                 "rationale": "x", "excerpt": "y", "page": 1, "confidence": 0.9}
            for pr in principles for c in pr["criteria"]}


for key in ("ENVIRONMENTAL", "SOCIAL"):
    pr = pillars.get(key)["principles"]
    sc = scoring.score_run(full_findings(pr), docs("A", "B"), set(), pr)
    rows = [r for p in sc["principles"] for r in p["criteria"]]
    check(f"{key.lower()} scores with the same engine",
          sc["result"]["band"] == "LEADING" and all(r["criterionCode"][0] == key[0] for r in rows))
    empty = scoring.score_run({}, docs("B"), set(), pr)
    check(f"{key.lower()} with no findings declines to rate",
          empty["result"]["band"] == "INSUFFICIENT_EVIDENCE")

section("NEW SOURCE GRADES")
check("a climate statement grades A", scoring.grade_for("climate_statement", "native") == "A")
check("a modern slavery statement grades B",
      scoring.grade_for("modern_slavery_statement", "native") == "B")
check("a document provided on request grades C, below anything published",
      scoring.grade_for("company_response", "native") == "C")

done()
