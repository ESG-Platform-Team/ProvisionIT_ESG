"""
The deterministic scoring engine.

No model is called from this file and none ever should be. The LLM proposes,
this code decides. That is what makes a rating reproducible, auditable and
cheap, and it is the sentence to say if anyone asks how the platform can be
defensible when part of it is a language model.

Three rules encoded here, all of them client-confirmed:

Source quality never enters a score. SourceGrade is aggregated separately and
carried out as a confidence letter beside the band.

Missing data is five states, not one. An evidence gap is a statement about our
coverage. NOT_DISCLOSED is a statement about the company. They are never
collapsed and neither becomes a maturity of zero.

Transparency and practice are never averaged. Mick's answer to question six was
that the information should be there, so both are computed and both are
returned.
"""

from __future__ import annotations

from .matrix import MATURITY_LABELS, PRINCIPLES

# Practice bands, applied to mean maturity across in-scope criteria.
BAND_THRESHOLDS = [
    (3.4, "LEADING"),
    (2.2, "ESTABLISHED"),
    (1.4, "DEVELOPING"),
    (0.5, "MINIMAL"),
    (0.0, "NOT_EVIDENCED"),
]

# Below this share of in-scope criteria actually reachable, we decline to rate.
# Mick confirmed refusing is a strength, so it is a threshold rather than a
# best effort.
MIN_COVERAGE_TO_RATE = 0.55

GRADE_POINTS = {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0}
POINTS_GRADE = [(3.5, "A"), (2.5, "B"), (1.5, "C"), (0.5, "D"), (0.0, "E")]

# Source grade by document type. Company published and audited is A, company
# published unaudited is B, website text is C. Assigned to the document, never
# to the finding, so it cannot leak into the score.
SOURCE_GRADES = {
    "annual_report": "A",
    "remuneration_report": "A",
    "governance_statement": "B",
    "board_charter": "B",
    "audit_charter": "B",
    "nomination_charter": "B",
    "risk_charter": "B",
    "remuneration_charter": "B",
    "code_of_conduct": "B",
    "whistleblower_policy": "B",
    "anti_bribery_policy": "B",
    "diversity_policy": "B",
    "disclosure_policy": "B",
    "constitution": "B",
    "notice_of_meeting": "B",
    "agm_results": "B",
    "sustainability_report": "B",
    "webpage": "C",
}


def grade_for(source_type: str, extraction_method: str) -> str:
    """Grade the document. OCR recovered text drops one grade because the text
    layer is reconstructed rather than read, which is a statement about our
    retrieval and not about the company."""
    base = SOURCE_GRADES.get(source_type, "C")
    if extraction_method == "ocr":
        order = ["A", "B", "C", "D", "E"]
        return order[min(order.index(base) + 1, 4)]
    return base


def score_run(findings_by_code: dict, documents: list, retrieval_failed: set[str]) -> dict:
    """findings_by_code maps criterionCode to a raw finding dict from llm.py.
    retrieval_failed holds criterion codes whose expected source could not be
    retrieved at all."""

    criterion_results: list[dict] = []
    principle_summaries: list[dict] = []

    in_scope = 0
    disclosed = 0
    evidenced = 0
    maturity_sum = 0.0
    maturity_n = 0
    gaps = 0
    not_applicable = 0

    for principle in PRINCIPLES:
        rows = []
        for c in principle["criteria"]:
            code = c["criterionCode"]
            raw = findings_by_code.get(code)
            row = _resolve(c, raw, code in retrieval_failed)
            rows.append(row)

            if row["status"] == "NOT_APPLICABLE":
                not_applicable += 1
                continue

            in_scope += 1
            if row["status"] == "EVIDENCE_GAP":
                gaps += 1
                continue

            if row["status"] in ("DISCLOSED", "NOT_DISCLOSED_EXPLAINED"):
                disclosed += 1
            if row["status"] == "DISCLOSED":
                evidenced += 1

            if row["maturity"] is not None:
                maturity_sum += row["maturity"] * c["weight"]
                maturity_n += c["weight"]

        criterion_results.extend(rows)
        principle_summaries.append(_principle_band(principle, rows))

    coverage = ((in_scope - gaps) / in_scope) if in_scope else 0.0
    confidence = _confidence(documents)

    if in_scope == 0 or coverage < MIN_COVERAGE_TO_RATE:
        result = {
            "band": "INSUFFICIENT_EVIDENCE",
            "confidence": confidence,
            "transparencyScore": {
                "value": None, "unit": "PROPORTION",
                "basis": "Coverage too thin to report a transparency figure",
            },
            "practiceScore": {
                "value": None, "unit": "MATURITY_MEAN", "max": 4,
                "basis": "Coverage too thin to report a practice figure",
            },
            "declineReason": (
                f"Only {in_scope - gaps} of {in_scope} in-scope criteria could be "
                f"reached, below the {int(MIN_COVERAGE_TO_RATE * 100)}% threshold "
                "required to defend a band."
            ),
        }
    else:
        transparency = disclosed / in_scope
        practice = maturity_sum / maturity_n if maturity_n else 0.0
        result = {
            "band": _band(practice),
            "confidence": confidence,
            "transparencyScore": {
                "value": round(transparency, 3), "unit": "PROPORTION",
                "basis": (
                    "Share of in-scope criteria where the company published "
                    "something we could locate and cite"
                ),
            },
            "practiceScore": {
                "value": round(practice, 2), "unit": "MATURITY_MEAN", "max": 4,
                "basis": (
                    "Mean maturity of what the disclosures describe, judged "
                    "against the matrix, not how much was said"
                ),
            },
            "declineReason": None,
        }

    result["counts"] = {
        "criteriaInScope": in_scope,
        "findingsEvidenced": evidenced,
        "notApplicable": not_applicable,
        "evidenceGaps": gaps,
        "sourcesRetrieved": sum(1 for d in documents if d.get("outcome") == "RETRIEVED"),
        "sourcesAttempted": len(documents),
    }
    return {
        "result": result,
        "criterionResults": criterion_results,
        "principles": principle_summaries,
    }


def _resolve(criterion: dict, raw: dict | None, retrieval_failed: bool) -> dict:
    """One raw finding becomes one CriterionResult. This is where the five-value
    enum is actually applied, and it is the only place it should be."""
    code = criterion["criterionCode"]

    if raw is None or retrieval_failed:
        # We never reached a source that could answer this. A statement about
        # our coverage, not about the company.
        return _row(code, criterion, "EVIDENCE_GAP", None,
                    "Expected source could not be retrieved", None, [])

    excerpt = (raw.get("excerpt") or "").strip()
    page = raw.get("page") or 0
    rationale = (raw.get("rationale") or "").strip()
    confidence = raw.get("confidence")

    if raw.get("explainedDeparture"):
        # Legitimate conduct under "if not, why not". Counts toward transparency
        # only, per Mick's answer to question eight. maturity stays None so it
        # cannot drag the practice mean down.
        return _row(code, criterion, "NOT_DISCLOSED_EXPLAINED", None,
                    rationale or "Departure disclosed with reasons",
                    confidence, _evidence(excerpt, page))

    if not raw.get("found"):
        return _row(code, criterion, "NOT_DISCLOSED", None,
                    rationale or "Not addressed in the retrieved documents",
                    confidence, [])

    signal = raw.get("maturitySignal", "STATED")
    maturity = MATURITY_LABELS.index(signal) if signal in MATURITY_LABELS else 1

    if maturity == 0:
        # The model says it found something but rated the practice at none.
        # Treat that as not disclosed rather than a zero, since a zero would
        # silently become a low band.
        return _row(code, criterion, "NOT_DISCLOSED", None,
                    rationale or "Topic mentioned, practice not evidenced",
                    confidence, _evidence(excerpt, page))

    return _row(code, criterion, "DISCLOSED", maturity, rationale, confidence,
                _evidence(excerpt, page))


def _row(code, criterion, status, maturity, rationale, confidence, evidence) -> dict:
    grade = evidence[0]["sourceGrade"] if evidence else None
    return {
        "criterionCode": code,
        "recommendationCode": criterion["recommendationCode"],
        "question": criterion["question"],
        "status": status,
        "maturity": maturity,
        "maturityLabel": MATURITY_LABELS[maturity] if maturity is not None else None,
        # Mick's combined notation. Maturity and evidence grade shown together,
        # never multiplied together.
        "notation": f"{maturity}{grade}" if maturity is not None and grade else None,
        "rationale": rationale,
        "overridden": False,
        "extractionConfidence": confidence,
        "evidence": evidence,
    }


def _evidence(excerpt: str, page: int) -> list[dict]:
    if not excerpt:
        return []
    return [{
        "excerpt": excerpt,
        "locator": f"p.{page}" if page else "location not recorded",
        "page": page,
        "sourceGrade": None,   # filled in by the pipeline once the document is known
        "sourceDocumentId": None,
        "extractedBy": "LLM",
    }]


def _band(practice_mean: float) -> str:
    for threshold, name in BAND_THRESHOLDS:
        if practice_mean >= threshold:
            return name
    return "NOT_EVIDENCED"


def _principle_band(principle: dict, rows: list[dict]) -> str | dict:
    scoped = [r for r in rows if r["status"] != "NOT_APPLICABLE"]
    if scoped and all(r["status"] == "NOT_DISCLOSED_EXPLAINED" for r in scoped):
        band = "DEPARTS_EXPLAINED"
    else:
        rated = [r["maturity"] for r in scoped if r["maturity"] is not None]
        band = _band(sum(rated) / len(rated)) if rated else "NOT_EVIDENCED"
    return {
        "number": principle["number"],
        "title": principle["title"],
        "band": band,
        "criteria": rows,
    }


def _confidence(documents: list) -> str:
    """Aggregate source grade across the documents that actually produced text.
    Separate from the band, reported beside it, never folded in."""
    grades = [d["sourceGrade"] for d in documents
              if d.get("outcome") == "RETRIEVED" and d.get("sourceGrade")]
    if not grades:
        return "E"
    mean = sum(GRADE_POINTS.get(g, 0) for g in grades) / len(grades)
    for threshold, letter in POINTS_GRADE:
        if mean >= threshold:
            return letter
    return "E"
