"""
Shared helpers for the offline test files. No network, no API key, no cost.

Each test_*.py file imports check() from here and ends with done(), which exits
non-zero if anything failed, so CI and a plain `python test_x.py` agree.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

_counts = {"pass": 0, "fail": 0}


def check(name, condition, detail=""):
    if condition:
        _counts["pass"] += 1
        print(f"  pass  {name}")
    else:
        _counts["fail"] += 1
        print(f"  FAIL  {name}  {detail}")


def raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


def docs(*grades, outcome="RETRIEVED"):
    return [{"outcome": outcome, "sourceGrade": g} for g in grades]


def section(title):
    print(f"\n{title}")


def done():
    print(f"\n{_counts['pass']} passed, {_counts['fail']} failed\n")
    raise SystemExit(1 if _counts["fail"] else 0)
