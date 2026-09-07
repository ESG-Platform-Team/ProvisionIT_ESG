#!/usr/bin/env python3
"""
Run one assessment end to end and print it. This is the demo.

    python run_cli.py BEN
    python run_cli.py BHP --no-llm
    python run_cli.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import companies, pipeline  # noqa: E402

BAR = "=" * 78
DASH = "-" * 78

STATUS_MARK = {
    "DISCLOSED": "evidenced",
    "NOT_DISCLOSED": "not disclosed",
    "NOT_DISCLOSED_EXPLAINED": "departs, explained",
    "NOT_APPLICABLE": "not required",
    "EVIDENCE_GAP": "not retrieved",
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asx_code", nargs="?", help="ASX code, for example BEN")
    ap.add_argument("--no-llm", action="store_true",
                    help="Keyword extraction only, no Gemini calls")
    ap.add_argument("--max-docs", type=int, default=12)
    ap.add_argument("--json", metavar="PATH", help="Also write the full result to a file")
    ap.add_argument("--list", action="store_true", help="List seeded companies")
    args = ap.parse_args()

    if args.list or not args.asx_code:
        print("\nSeeded companies:\n")
        for c in companies.COMPANIES:
            print(f"  {c['asxCode']:<5} {c['name']:<34} {c['website']}")
        print()
        return 0

    company = companies.get(args.asx_code)
    if company is None:
        print(f"Unknown code {args.asx_code}. Try --list.")
        return 1

    use_llm = not args.no_llm
    if use_llm and not os.getenv("GEMINI_API_KEY"):
        print("\nGEMINI_API_KEY is not set, so this run uses keyword extraction only.")
        print("Keyword matching finds topics, not practices, so every finding it")
        print("returns is capped at STATED. Set the key for a real assessment.\n")
        use_llm = False

    print(f"\n{BAR}")
    print(f"  {company['name']}  ({company['asxCode']})")
    print(f"  {'Gemini ' + os.getenv('GEMINI_MODEL', 'gemini-2.5-flash') if use_llm else 'Keyword extraction, no LLM'}")
    print(BAR)

    state = pipeline.RunState(pipeline.new_run_id(), company)
    result = await pipeline.run_assessment(
        company, state, use_llm=use_llm, max_docs=args.max_docs
    )

    _print_result(result)

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2))
        print(f"\nFull result written to {args.json}")
    return 0


def _print_result(r: dict) -> None:
    res = r["result"]
    counts = res["counts"]

    print(f"\n{BAR}")
    print(f"  GOVERNANCE BAND   {res['band']}        CONFIDENCE  {res['confidence']}")
    print(BAR)

    if res.get("declineReason"):
        print(f"\n  {res['declineReason']}\n")
    else:
        t = res["transparencyScore"]["value"]
        p = res["practiceScore"]["value"]
        print(f"\n  Transparency   {t * 100:5.1f}%    share of in-scope criteria disclosed")
        print(f"  Practice       {p:5.2f}/4   mean maturity of what was disclosed")

    print(f"\n  {counts['criteriaInScope']:>3}  criteria in scope")
    print(f"  {counts['findingsEvidenced']:>3}  findings evidenced")
    print(f"  {counts['notApplicable']:>3}  not required")
    print(f"  {counts['evidenceGaps']:>3}  evidence gaps")
    print(f"  {counts['sourcesRetrieved']:>3}/{counts['sourcesAttempted']} sources retrieved")

    print(f"\n{DASH}\n  SOURCE LOG\n{DASH}")
    for d in r["sourceLog"]:
        grade = f"[{d['sourceGrade']}]" if d.get("sourceGrade") else "   "
        method = d.get("extractionMethod") or ""
        print(f"  {d['outcome']:<11} {grade} {d['title'][:44]:<46} {method}")

    print(f"\n{DASH}\n  FINDINGS\n{DASH}")
    for principle in r["principles"]:
        print(f"\n  {principle['number']:02d}  {principle['title']}")
        print(f"      {principle['band']}")
        for row in principle["criteria"]:
            note = f"  {row['notation']}" if row.get("notation") else "    "
            print(f"      {row['criterionCode']:<6}{note}  {STATUS_MARK[row['status']]:<19}"
                  f"{(row['rationale'] or '')[:38]}")
            for ev in row["evidence"]:
                print(f"             \"{ev['excerpt'][:66]}\"")
                print(f"              {ev['locator']}")
    print()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
