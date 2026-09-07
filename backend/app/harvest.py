"""
Harvesting public governance documents.

Three rules this module never breaks, because they are the project's ethical
constraints rather than implementation preferences:

1. robots.txt is checked before every fetch and the result is recorded on the
   HarvestTask, not swallowed. A disallowed URL produces a task with
   robotsAllowed=False and no document, which is a finding.
2. Only free public sources. No login, no paywall, no paid API.
3. A polite delay between requests to the same host, and a real User-Agent that
   identifies the project so a site owner can contact us.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "ProvisionIT-GovernanceBot/0.1 "
    "(University of Melbourne COMP30033 capstone; contact mick.both@gmail.com)"
)

# Delay between requests to the same host. Mick's sources are free and public,
# and hammering them is both discourteous and a fast route to an IP block.
HOST_DELAY_SECONDS = 1.5

# Link text or href fragments that suggest a governance document.
DOC_PATTERNS = [
    ("governance_statement", r"corporate[- ]governance[- ]statement|governance[- ]statement"),
    ("annual_report", r"annual[- ]report"),
    ("board_charter", r"board[- ]charter"),
    ("audit_charter", r"audit.{0,20}charter|audit.{0,20}committee.{0,20}charter"),
    ("nomination_charter", r"nomination.{0,20}charter"),
    ("risk_charter", r"risk.{0,20}charter|risk.{0,20}committee.{0,20}charter"),
    ("remuneration_charter", r"remuneration.{0,20}charter|people.{0,20}charter"),
    ("code_of_conduct", r"code[- ]of[- ]conduct|code[- ]of[- ]business[- ]conduct"),
    ("whistleblower_policy", r"whistleblow"),
    ("anti_bribery_policy", r"anti[- ]bribery|bribery[- ]and[- ]corruption"),
    ("diversity_policy", r"diversity[- ](policy|and[- ]inclusion)"),
    ("disclosure_policy", r"continuous[- ]disclosure|disclosure[- ]policy"),
    ("remuneration_report", r"remuneration[- ]report"),
    ("sustainability_report", r"sustainability[- ]report|esg[- ]report|climate[- ]report"),
    ("constitution", r"constitution"),
    ("notice_of_meeting", r"notice[- ]of[- ](annual[- ])?meeting"),
    ("agm_results", r"results[- ]of[- ]meeting|agm[- ]results|voting[- ]results"),
]

# Pages likely to link to the documents above.
HUB_PATTERNS = r"governance|investor|about[- ]us|leadership|board|polic|sustainab|shareholder"


@dataclass
class HarvestTask:
    """One fetch attempt against one URL. Mirrors the HarvestTask class on the
    domain model, including robotsAllowed sitting in the domain rather than in
    scraper config."""

    target_url: str
    source_type: str
    robots_allowed: bool | None = None
    status: str = "PENDING"  # PENDING RETRIEVED NOT_FOUND BLOCKED UNREADABLE
    attempts: int = 0
    http_status: int | None = None
    elapsed_ms: int | None = None
    note: str = ""


@dataclass
class SourceDocument:
    """What we actually fetched and kept. content_hash powers change detection
    and the extraction cache."""

    url: str
    source_type: str
    title: str
    media_type: str
    content: bytes
    content_hash: str
    retrieved_at: float
    published_date: str | None = None
    publisher: str | None = None
    http_status: int = 200
    elapsed_ms: int = 0
    robots_allowed: bool = True
    text: str = ""
    pages: list[str] = field(default_factory=list)

    @property
    def short_hash(self) -> str:
        return self.content_hash[:12]


class RobotsCache:
    """One robots.txt lookup per host, reused for the rest of the run."""

    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser | None] = {}

    async def allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self._cache:
            self._cache[host] = await self._load(client, url)
        rp = self._cache[host]
        if rp is None:
            # No robots.txt, or it could not be read. Absence of a rule is
            # permission under the standard, but we still rate limit.
            return True
        return rp.can_fetch(USER_AGENT, url)

    async def _load(self, client: httpx.AsyncClient, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            res = await client.get(robots_url, timeout=10.0)
            if res.status_code != 200:
                return None
            rp = RobotFileParser()
            rp.parse(res.text.splitlines())
            return rp
        except httpx.HTTPError:
            return None


class Harvester:
    def __init__(self, delay: float = HOST_DELAY_SECONDS, max_docs: int = 14) -> None:
        self.robots = RobotsCache()
        self.delay = delay
        self.max_docs = max_docs
        self._last_hit: dict[str, float] = {}
        self.tasks: list[HarvestTask] = []

    async def _polite_wait(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_hit.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.delay:
                await asyncio.sleep(self.delay - gap)
        self._last_hit[host] = time.monotonic()

    async def fetch(
        self, client: httpx.AsyncClient, url: str, source_type: str, title: str = ""
    ) -> tuple[HarvestTask, SourceDocument | None]:
        task = HarvestTask(target_url=url, source_type=source_type)

        task.robots_allowed = await self.robots.allowed(client, url)
        if not task.robots_allowed:
            task.status = "BLOCKED"
            task.note = "Disallowed by robots.txt"
            self.tasks.append(task)
            return task, None

        await self._polite_wait(url)
        started = time.monotonic()
        task.attempts = 1
        try:
            res = await client.get(url, timeout=45.0, follow_redirects=True)
        except httpx.HTTPError as exc:
            task.status = "NOT_FOUND"
            task.note = f"{type(exc).__name__}"
            task.elapsed_ms = int((time.monotonic() - started) * 1000)
            self.tasks.append(task)
            return task, None

        task.http_status = res.status_code
        task.elapsed_ms = int((time.monotonic() - started) * 1000)

        if res.status_code != 200 or not res.content:
            task.status = "NOT_FOUND"
            task.note = f"HTTP {res.status_code}"
            self.tasks.append(task)
            return task, None

        media = res.headers.get("content-type", "").split(";")[0].strip().lower()
        task.status = "RETRIEVED"
        doc = SourceDocument(
            url=str(res.url),
            source_type=source_type,
            title=title or _title_from_url(url),
            media_type=media or "application/octet-stream",
            content=res.content,
            content_hash=hashlib.sha256(res.content).hexdigest(),
            retrieved_at=time.time(),
            publisher=urlparse(url).netloc,
            http_status=res.status_code,
            elapsed_ms=task.elapsed_ms,
            robots_allowed=True,
        )
        self.tasks.append(task)
        return task, doc

    async def discover(self, client: httpx.AsyncClient, root_url: str) -> list[dict]:
        """Crawl the company site shallowly and return candidate documents.

        Depth is deliberately two: the root, then any governance or investor hub
        page linked from it. Deeper crawling finds marginally more and costs a
        lot more requests against someone else's server.
        """
        found: dict[str, dict] = {}
        pages_to_scan = [root_url]
        seen_pages: set[str] = set()

        for depth in range(2):
            next_pages: list[str] = []
            for page in pages_to_scan:
                if page in seen_pages:
                    continue
                seen_pages.add(page)
                _, doc = await self.fetch(client, page, "webpage", "")
                if doc is None or "html" not in doc.media_type:
                    continue
                soup = BeautifulSoup(doc.content, "lxml")
                for a in soup.find_all("a", href=True):
                    href = urljoin(page, a["href"].strip())
                    if not href.startswith("http"):
                        continue
                    if urlparse(href).netloc != urlparse(root_url).netloc:
                        continue
                    label = " ".join(a.get_text(" ", strip=True).split()).lower()
                    haystack = f"{label} {href.lower()}"

                    matched = _classify(haystack)
                    if matched and href not in found:
                        found[href] = {
                            "url": href,
                            "source_type": matched,
                            "title": a.get_text(" ", strip=True)[:120] or _title_from_url(href),
                            "is_pdf": href.lower().split("?")[0].endswith(".pdf"),
                        }
                    elif depth == 0 and re.search(HUB_PATTERNS, haystack):
                        if href not in seen_pages and len(next_pages) < 6:
                            next_pages.append(href)
            pages_to_scan = next_pages

        # A PDF of the governance statement beats an HTML page describing it.
        ranked = sorted(
            found.values(),
            key=lambda d: (not d["is_pdf"], _type_rank(d["source_type"])),
        )
        return ranked[: self.max_docs]


def _classify(haystack: str) -> str | None:
    for source_type, pattern in DOC_PATTERNS:
        if re.search(pattern, haystack):
            return source_type
    return None


def _type_rank(source_type: str) -> int:
    order = [t for t, _ in DOC_PATTERNS]
    return order.index(source_type) if source_type in order else 99


def _title_from_url(url: str) -> str:
    tail = urlparse(url).path.rstrip("/").split("/")[-1] or urlparse(url).netloc
    return re.sub(r"[-_]+", " ", tail).replace(".pdf", "").strip().title()


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        follow_redirects=True,
    )
