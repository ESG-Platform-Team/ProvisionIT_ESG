#!/usr/bin/env python3
"""
Offline tests. No network, no API key, no cost.

These run the scoring engine against fixed findings, which is only possible
because scoring is deterministic and LLM free. That property is the reason the
engine is testable at all, and it is worth saying at a review.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import llm, scoring, textract  # noqa: E402
from app.matrix import PRINCIPLES  # noqa: E402

PASS, FAIL = 0, 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  pass  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


SAMPLE = [
    "Corporate Governance Statement 2026. This statement was approved by the board.",
    "The board charter sets out the respective roles and responsibilities of the "
    "board, the chair and management. The charter is reviewed annually and is "
    "available on our website. A nomination committee of four directors, three of "
    "whom are independent, operates under a disclosed charter.",
    "The company has adopted a whistleblower policy. Material incidents are "
    "reported to the audit committee at each scheduled meeting.",
]


def docs(*grades, outcome="RETRIEVED"):
    return [{"outcome": outcome, "sourceGrade": g} for g in grades]


print("\nEXTRACTION WINDOWS")
w = textract.windows_for(SAMPLE, ["board charter", "whistleblower"])
check("finds passages on the right pages", {p for p, _ in w} == {2, 3}, f"got {[p for p, _ in w]}")
check("returns no passages when nothing matches",
      textract.windows_for(SAMPLE, ["carbon offset registry"]) == [])
capped = textract.windows_for(SAMPLE, ["board"], max_chars=50)
check("respects the character budget", sum(len(t) for _, t in capped) <= 50)

print("\nKEYWORD FALLBACK")
passages = [("Gov statement", p, t) for p, t in enumerate(SAMPLE, 1)]
kf = llm.keyword_findings(PRINCIPLES[0], passages)
check("returns one finding per criterion", len(kf) == len(PRINCIPLES[0]["criteria"]))
check("caps everything it finds at STATED",
      all(f["maturitySignal"] in ("NONE", "STATED") for f in kf))
check("never claims high confidence", all(f["confidence"] <= 0.5 for f in kf))

print("\nSCORING, THE FIVE STATUSES")
found = {"criterionCode": "G1.1", "found": True, "explainedDeparture": False,
         "maturitySignal": "MONITORED", "rationale": "charter reviewed annually",
         "excerpt": "The board charter sets out the respective roles", "page": 2,
         "confidence": 0.9}
s = scoring.score_run({"G1.1": found}, docs("A", "B"), set())
row = next(r for r in s["criterionResults"] if r["criterionCode"] == "G1.1")
check("a supported finding is DISCLOSED", row["status"] == "DISCLOSED")
check("MONITORED maps to maturity 3", row["maturity"] == 3)
check("notation combines maturity and grade", row["notation"] is None or row["notation"][0] == "3")

gap_row = next(r for r in s["criterionResults"] if r["criterionCode"] == "G7.3")
check("an unreached criterion is EVIDENCE_GAP", gap_row["status"] == "EVIDENCE_GAP")
check("an evidence gap has no maturity, not a zero", gap_row["maturity"] is None)
check("an evidence gap carries no evidence", gap_row["evidence"] == [])

departed = {"criterionCode": "G8.1", "found": True, "explainedDeparture": True,
            "maturitySignal": "STATED", "rationale": "board of five handles remuneration",
            "excerpt": "The board does not maintain a separate committee", "page": 29,
            "confidence": 0.9}
s2 = scoring.score_run({"G8.1": departed}, docs("A"), set())
dep = next(r for r in s2["criterionResults"] if r["criterionCode"] == "G8.1")
check("an explained departure is its own status",
      dep["status"] == "NOT_DISCLOSED_EXPLAINED")
check("an explained departure has no maturity, so it cannot drag practice down",
      dep["maturity"] is None)

zeroed = {"criterionCode": "G1.1", "found": True, "explainedDeparture": False,
          "maturitySignal": "NONE", "rationale": "mentioned only", "excerpt": "board",
          "page": 1, "confidence": 0.5}
s3 = scoring.score_run({"G1.1": zeroed}, docs("B"), set())
z = next(r for r in s3["criterionResults"] if r["criterionCode"] == "G1.1")
check("a NONE signal becomes NOT_DISCLOSED, never maturity zero",
      z["status"] == "NOT_DISCLOSED" and z["maturity"] is None)

print("\nSCORING, THE HEADLINE")
full = {}
for pr in PRINCIPLES:
    for c in pr["criteria"]:
        full[c["criterionCode"]] = {
            "criterionCode": c["criterionCode"], "found": True,
            "explainedDeparture": False, "maturitySignal": "EMBEDDED",
            "rationale": "x", "excerpt": "y", "page": 1, "confidence": 0.9}
s4 = scoring.score_run(full, docs("A", "A", "A"), set())
check("all embedded produces LEADING", s4["result"]["band"] == "LEADING")
check("transparency reaches 1.0", s4["result"]["transparencyScore"]["value"] == 1.0)
check("practice reaches 4.0", s4["result"]["practiceScore"]["value"] == 4.0)
check("confidence letter is separate from the band", s4["result"]["confidence"] == "A")

print("\nSCORING, DECLINING TO RATE")
s5 = scoring.score_run({}, docs("C", outcome="NOT_FOUND"), set())
check("no findings at all means INSUFFICIENT_EVIDENCE",
      s5["result"]["band"] == "INSUFFICIENT_EVIDENCE")
check("a declined run reports no transparency figure",
      s5["result"]["transparencyScore"]["value"] is None)
check("a declined run explains why", bool(s5["result"]["declineReason"]))

thin = {k: v for i, (k, v) in enumerate(full.items()) if i < 12}
s6 = scoring.score_run(thin, docs("B"), set())
check("thin coverage still declines rather than guessing",
      s6["result"]["band"] == "INSUFFICIENT_EVIDENCE")

print("\nSOURCE QUALITY NEVER ENTERS THE SCORE")
good = scoring.score_run(full, docs("A", "A"), set())
poor = scoring.score_run(full, docs("D", "D"), set())
check("identical findings give identical practice regardless of source grade",
      good["result"]["practiceScore"]["value"] == poor["result"]["practiceScore"]["value"])
check("identical findings give identical transparency regardless of source grade",
      good["result"]["transparencyScore"]["value"] == poor["result"]["transparencyScore"]["value"])
check("identical findings give the same band regardless of source grade",
      good["result"]["band"] == poor["result"]["band"])
check("but the confidence letter does move",
      good["result"]["confidence"] != poor["result"]["confidence"])

print("\nSOURCE GRADING")
check("an audited annual report grades A", scoring.grade_for("annual_report", "native") == "A")
check("a governance statement grades B", scoring.grade_for("governance_statement", "native") == "B")
check("website text grades C", scoring.grade_for("webpage", "html") == "C")
check("OCR recovery costs one grade", scoring.grade_for("annual_report", "ocr") == "B")

print(f"\n{PASS} passed, {FAIL} failed\n")
raise SystemExit(1 if FAIL else 0)
