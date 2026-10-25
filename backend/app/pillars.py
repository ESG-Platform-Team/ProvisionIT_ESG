"""
The three pillars, as one registry.

Each pillar is a matrix module with the same shape, so the harvest, the model
call and the scoring engine are shared and nothing downstream branches on which
pillar it is handling. Adding a fourth set of criteria is a new module and one
line here.
"""

from __future__ import annotations

from . import matrix, matrix_environmental, matrix_social

_MODULES = {
    "GOVERNANCE": matrix,
    "ENVIRONMENTAL": matrix_environmental,
    "SOCIAL": matrix_social,
}

ORDER = ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"]


def get(pillar: str) -> dict:
    key = (pillar or "GOVERNANCE").upper()
    mod = _MODULES.get(key)
    if mod is None:
        raise KeyError(f"Unknown pillar {pillar}")
    return {
        "pillar": mod.PILLAR,
        "label": mod.LABEL,
        "matrixVersion": mod.MATRIX_VERSION,
        "frameworkEdition": mod.FRAMEWORK_EDITION,
        "frameworkName": mod.FRAMEWORK_NAME,
        "unitName": mod.UNIT_NAME,
        "principles": mod.PRINCIPLES,
        "draft": "draft" in mod.MATRIX_VERSION.lower(),
    }


def normalise(requested: list[str] | str | None) -> list[str]:
    """Accept one pillar, a list, or 'ALL', and return them in display order."""
    if requested is None:
        return ["GOVERNANCE"]
    if isinstance(requested, str):
        requested = [requested]
    wanted = {p.upper() for p in requested}
    if "ALL" in wanted:
        return list(ORDER)
    unknown = wanted - set(ORDER)
    if unknown:
        raise KeyError(f"Unknown pillar {sorted(unknown)[0]}")
    return [p for p in ORDER if p in wanted] or ["GOVERNANCE"]


def criterion(code: str) -> tuple[str, dict] | None:
    """Find a criterion in any pillar. Codes are prefixed G, E or S, so they are
    unique across the three matrices, which a test enforces."""
    for key in ORDER:
        for principle in get(key)["principles"]:
            for c in principle["criteria"]:
                if c["criterionCode"].lower() == code.lower():
                    return key, c
    return None
