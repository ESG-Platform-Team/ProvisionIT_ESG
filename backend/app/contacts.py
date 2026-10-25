"""
Find the contact addresses a company publishes on its own website, so an
analyst can choose who receives a disclosure request.

Rules, deliberately narrow:
- Only the company's own website is read, and robots.txt is respected (the
  harvester's fetch does both).
- Only addresses the company has published are returned: mailto links and
  addresses written on the page. Nothing is guessed or pattern-generated, and
  no other site is searched.
- Shared role inboxes (sustainability, investor relations, company secretary,
  privacy, general enquiries) are ranked first. An address that looks personal
  is still shown, labelled as such, because the analyst decides.
- Nothing is stored or emailed automatically. The analyst picks one.

Under the Spam Act 2003 an address a business conspicuously publishes can
generally be emailed about that business; guessed or harvested personal
addresses cannot. Provision IT should confirm its own position before real
requests are sent.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from . import harvest

EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
PAGE_HINTS = re.compile(r"contact|investor|sharehold|sustainab|esg|environment|governance|"
                        r"privacy|about|company-secretary|corporate|enquir", re.I)
NOT_EMAIL = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js)$", re.I)
MAX_PAGES = 10

# (role, rank) by local part. Lower rank is shown first.
ROLES = [
    (re.compile(r"sustainab|esg|environment|climate|csr|impact", re.I), "Sustainability", 0),
    (re.compile(r"investor|^ir$|^ir\.|sharehold|shareregistry", re.I), "Investor relations", 1),
    (re.compile(r"cosec|secretar|company\.?sec|governance|board", re.I), "Company secretary", 2),
    (re.compile(r"privacy|dpo|dataprotection", re.I), "Privacy officer", 3),
    (re.compile(r"^(info|contact|enquir|hello|admin|office|reception|general|mail)", re.I),
     "General enquiries", 4),
    (re.compile(r"media|press|comms|communications", re.I), "Media", 5),
    (re.compile(r"careers|jobs|recruit|hr$|support|help|sales|accounts|billing|noreply|no-reply",
                re.I), "Not suitable", 9),
]


def _role(local: str) -> tuple[str, int]:
    for pattern, role, rank in ROLES:
        if pattern.search(local):
            return role, rank
    return "May be a personal address", 7


def _site(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    # example.com.au -> example.com.au, shop.example.com -> example.com
    return ".".join(parts[-3:]) if len(parts) > 2 and len(parts[-1]) == 2 else ".".join(parts[-2:])


def _emails_in(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    found = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            found.append(unquote(href[7:].split("?")[0]))
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s*\[\s*at\s*\]\s*|\s+\(at\)\s+", "@", text, flags=re.I)
    found += EMAIL.findall(text)
    return [f.strip().strip(".,;:").lower() for f in found if f]


async def find(website: str) -> dict:
    """Crawl the homepage and the pages it links to that usually carry
    contacts, and return every published address with where it was found."""
    hv = harvest.Harvester(delay=0.5)
    root = website.rstrip("/")
    site = _site(root)
    seen_pages, queue, results = set(), [root], {}
    async with harvest.new_client() as client:
        while queue and len(seen_pages) < MAX_PAGES:
            url = queue.pop(0)
            if url in seen_pages:
                continue
            seen_pages.add(url)
            _, doc = await hv.fetch(client, url, "webpage", "")
            if doc is None or "html" not in doc.media_type:
                continue
            for email in _emails_in(doc.content):
                if NOT_EMAIL.search(email) or email in results:
                    continue
                local, domain = email.split("@", 1)
                role, rank = _role(local)
                if domain != site and not domain.endswith("." + site):
                    rank += 2  # an address on another domain is less likely to be theirs
                results[email] = {"email": email, "role": role, "rank": rank,
                                  "source": doc.url, "sameDomain": domain.endswith(site)}
            if url == root:
                soup = BeautifulSoup(doc.content, "lxml")
                for a in soup.find_all("a", href=True):
                    href = urljoin(url, a["href"].strip()).split("#")[0]
                    label = f"{a.get_text(' ', strip=True)} {href}"
                    if (href.startswith("http") and _site(href) == site
                            and PAGE_HINTS.search(label) and href not in seen_pages
                            and not href.lower().endswith(".pdf")):
                        queue.append(href)
    contacts = sorted((c for c in results.values() if c["role"] != "Not suitable"),
                      key=lambda c: (c["rank"], c["email"]))
    return {"website": root, "pagesChecked": len(seen_pages), "contacts": contacts[:10]}
