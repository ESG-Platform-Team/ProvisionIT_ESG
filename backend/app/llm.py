"""
Gemini extraction.

The division of labour is the thing to protect here. The model reads documents
and reports what it found, with a quoted passage and a page number. It does not
decide a band, a score or a grade. Everything downstream of this file is
deterministic code in scoring.py, which is what makes a rating reproducible and
what stops us paying per token for arithmetic.

Quota shape on the free tier, as of mid 2026: Flash models run roughly 10 to 15
requests per minute and around 1,500 per day, and the Pro models are no longer
free. That is the reason for one call per principle rather than one per
criterion. Eight calls assesses a company. Thirty-one would not be meaningfully
better and would cost four times the quota.

One thing to raise with Mick before this touches a real client: prompts sent on
the free tier may be used by Google to improve their models. Everything we send
is already public governance material, so the exposure is low, but it is a
decision the client should make rather than one we make silently. The paid tier
removes the clause.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import time
from pathlib import Path

import httpx

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_RPM = int(os.getenv("GEMINI_RPM", "10"))

CACHE_DIR = Path(os.getenv("LLM_CACHE_DIR", "data/llm_cache"))

# Keyed by content hash plus matrix version, exactly as the DynamoDB extraction
# cache is in the AWS design. A hit means the LLM is never called.
CACHE_DIR.mkdir(parents=True, exist_ok=True)


FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterionCode": {"type": "string"},
                    "found": {"type": "boolean"},
                    "explainedDeparture": {"type": "boolean"},
                    "maturitySignal": {
                        "type": "string",
                        "enum": ["NONE", "STATED", "IMPLEMENTED", "MONITORED", "EMBEDDED"],
                    },
                    "rationale": {"type": "string"},
                    "excerpt": {"type": "string"},
                    "page": {"type": "integer"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "criterionCode", "found", "explainedDeparture",
                    "maturitySignal", "rationale", "excerpt", "page", "confidence",
                ],
            },
        }
    },
    "required": ["findings"],
}


SYSTEM_RULES = """You are reading published corporate governance material from an
ASX listed entity and reporting what is present in the text. You are not rating
the company and you are not forming an opinion about it.

Rules you must follow exactly:

1. Report only what the supplied passages actually say. If a criterion is not
   addressed in the passages, set found=false. Never infer a practice from the
   absence of a statement, and never infer it from what a company of this type
   usually does.
2. excerpt must be a verbatim span copied from the passages, at most 40 words.
   If found=false, excerpt must be an empty string.
3. page must be the page number given in the passage header the excerpt came
   from. If found=false, page must be 0.
4. explainedDeparture=true only when the text states the entity does not follow
   the recommendation AND gives a reason. Under the ASX "if not, why not" model
   that is legitimate conduct, not a failure, so do not treat it as absence.
5. maturitySignal describes how far the text shows the practice has gone:
   STATED means the entity says it does this.
   IMPLEMENTED means the text shows it actually happens, with specifics.
   MONITORED means the text shows it is measured or reviewed on a stated cycle.
   EMBEDDED means the text shows it is routine, with reporting over time.
   NONE means the passages do not support the practice at all.
6. confidence is your confidence in the extraction itself, 0 to 1. It is not a
   judgement about the company and it is not the quality of the source.

Return JSON only, matching the schema. No prose, no markdown fences."""


class RateLimiter:
    """Requests per minute, spaced rather than bursted, because the free tier
    measures a rolling window and a burst of eight parallel calls will 429."""

    def __init__(self, rpm: int) -> None:
        self.interval = 60.0 / max(1, rpm)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            gap = time.monotonic() - self._last
            if gap < self.interval:
                await asyncio.sleep(self.interval - gap)
            self._last = time.monotonic()


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 rpm: int = DEFAULT_RPM, use_cache: bool = True) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.limiter = RateLimiter(rpm)
        self.use_cache = use_cache
        self.calls_made = 0
        self.cache_hits = 0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def extract_principle(
        self, client: httpx.AsyncClient, principle: dict,
        passages: list[tuple[str, int, str]], matrix_version: str,
    ) -> list[dict]:
        """One call, one principle. passages are (document title, page, text)."""
        if not passages:
            return []

        prompt = _build_prompt(principle, passages)
        key = _cache_key(self.model, matrix_version, principle["number"], prompt)

        if self.use_cache:
            cached = _cache_read(key)
            if cached is not None:
                self.cache_hits += 1
                return cached

        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_RULES}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "responseSchema": FINDING_SCHEMA,
                "maxOutputTokens": 8192,
            },
        }

        data = await self._post(client, payload)
        findings = _parse(data)
        if self.use_cache:
            _cache_write(key, findings)
        return findings

    async def _post(self, client: httpx.AsyncClient, payload: dict) -> dict:
        if not self.configured:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Export it, or run with --no-llm to "
                "use keyword extraction only."
            )
        url = f"{API_ROOT}/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

        delay = 2.0
        for attempt in range(5):
            await self.limiter.wait()
            try:
                res = await client.post(url, headers=headers, json=payload, timeout=180.0)
            except httpx.HTTPError as exc:
                if attempt == 4:
                    raise RuntimeError(f"Gemini unreachable: {exc}") from exc
                await asyncio.sleep(delay + random.random())
                delay *= 2
                continue

            self.calls_made += 1
            if res.status_code == 200:
                return res.json()

            if res.status_code in (429, 500, 502, 503, 504):
                # Exponential backoff with jitter. Immediate retry on a 429
                # makes the rolling window worse, not better.
                if attempt == 4:
                    raise RuntimeError(
                        f"Gemini returned {res.status_code} after 5 attempts. "
                        "On the free tier this is usually the daily request cap."
                    )
                await asyncio.sleep(delay + random.random())
                delay *= 2
                continue

            raise RuntimeError(f"Gemini error {res.status_code}: {res.text[:300]}")
        raise RuntimeError("Gemini retries exhausted")


def _build_prompt(principle: dict, passages: list[tuple[str, int, str]]) -> str:
    criteria_block = "\n".join(
        f'- {c["criterionCode"]}: {c["question"]}' for c in principle["criteria"]
    )
    passage_block = "\n\n".join(
        f"[SOURCE: {title} | PAGE: {page}]\n{text}" for title, page, text in passages
    )
    return f"""ASX Corporate Governance Council, Principle {principle['number']}:
{principle['title']}

Assess each of these criteria against the passages below. Return one finding per
criterion, including the ones you cannot support.

CRITERIA
{criteria_block}

PASSAGES
{passage_block}"""


def _parse(data: dict) -> list[dict]:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError):
        return []
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return parsed.get("findings", []) if isinstance(parsed, dict) else []


def _cache_key(model: str, matrix_version: str, principle: int, prompt: str) -> str:
    raw = f"{model}|{matrix_version}|{principle}|{prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_read(key: str):
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _cache_write(key: str, findings: list[dict]) -> None:
    try:
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(findings, indent=2))
    except OSError:
        pass


def keyword_findings(principle: dict, passages: list[tuple[str, int, str]]) -> list[dict]:
    """No-LLM fallback. Honest about what it is: presence of a keyword is
    evidence that a topic is mentioned, not that a practice exists. Everything
    it finds is capped at STATED, and confidence is deliberately low."""
    hay = "\n".join(t for _, _, t in passages).lower()
    out = []
    for c in principle["criteria"]:
        hits = [k for k in c["keywords"] if k.lower() in hay]
        if not hits:
            out.append({
                "criterionCode": c["criterionCode"], "found": False,
                "explainedDeparture": False, "maturitySignal": "NONE",
                "rationale": "No keyword match in retrieved text", "excerpt": "",
                "page": 0, "confidence": 0.3,
            })
            continue
        page, excerpt = _first_hit(passages, hits[0])
        out.append({
            "criterionCode": c["criterionCode"], "found": True,
            "explainedDeparture": False, "maturitySignal": "STATED",
            "rationale": f"Keyword match on {', '.join(hits[:3])}",
            "excerpt": excerpt, "page": page, "confidence": 0.4,
        })
    return out


def _first_hit(passages, keyword: str) -> tuple[int, str]:
    for _, page, text in passages:
        idx = text.lower().find(keyword.lower())
        if idx >= 0:
            return page, " ".join(text[max(0, idx - 80): idx + 180].split())[:240]
    return 0, ""
