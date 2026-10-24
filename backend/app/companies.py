"""
Mick's confirmed test companies, plus room for the tougher targets he said would
come later.

contactEmail is the address a disclosure request goes to. It is set only for the
fixture. For a real company the analyst enters the published investor relations
or company secretary address when making the request, rather than the platform
holding a list of contacts.

These are starting points for discovery, not a hardcoded document list. The
harvester crawls the website and finds whatever governance material is actually
published, which is the behaviour we need to demonstrate. extraUrls exists for
the case where a document is published but not linked from anywhere the shallow
crawl reaches.

Private (unlisted) companies are added by an analyst with a name, website and
contact address, and are stored in the database. They are assessed the same
way, and are the main audience for disclosure requests, since they publish
far less.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

COMPANIES = [
    # Offline fixture. Serve fixture-site on port 8123 and this runs the whole
    # pipeline with no internet at all, which is how to rehearse a demo on
    # unreliable wifi and how the integration test runs.
    {"asxCode": "TST", "name": "Fixture Test Group", "sector": "Test",
     "tier": "Fixture", "website": "http://localhost:8123", "extraUrls": [],
     "contactEmail": "company.secretary@fixture-test.example", "listed": True},
    {"asxCode": "BHP", "name": "BHP Group", "sector": "Materials",
     "tier": "ASX 20", "website": "https://www.bhp.com", "extraUrls": [], "listed": True},
    {"asxCode": "FMG", "name": "Fortescue", "sector": "Materials",
     "tier": "ASX 50", "website": "https://www.fortescue.com", "extraUrls": [], "listed": True},
    {"asxCode": "COL", "name": "Coles Group", "sector": "Consumer Staples",
     "tier": "ASX 50", "website": "https://www.colesgroup.com.au", "extraUrls": [], "listed": True},
    {"asxCode": "WOW", "name": "Woolworths Group", "sector": "Consumer Staples",
     "tier": "ASX 50", "website": "https://www.woolworthsgroup.com.au", "extraUrls": [], "listed": True},
    {"asxCode": "CBA", "name": "Commonwealth Bank of Australia", "sector": "Financials",
     "tier": "ASX 20", "website": "https://www.commbank.com.au", "extraUrls": [], "listed": True},
    {"asxCode": "NAB", "name": "National Australia Bank", "sector": "Financials",
     "tier": "ASX 20", "website": "https://www.nab.com.au", "extraUrls": [], "listed": True},
    {"asxCode": "BEN", "name": "Bendigo and Adelaide Bank", "sector": "Financials",
     "tier": "ASX 200", "website": "https://www.bendigoadelaide.com.au", "extraUrls": [], "listed": True},
]


_EMAIL = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[A-Za-z]{2,}$")


class CompanyError(ValueError):
    pass


def _stored() -> list[dict]:
    from . import store
    return store.list_companies()


def all_companies() -> list[dict]:
    """The seed registry first, then every company added through the app."""
    seen = {c["asxCode"] for c in COMPANIES}
    return list(COMPANIES) + [c for c in _stored() if c["asxCode"] not in seen]


def find(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    everyone = all_companies()
    exact = [c for c in everyone if c["asxCode"].lower() == q]
    if exact:
        return exact
    host = _host(q) if "." in q else ""
    return [c for c in everyone
            if q in c["asxCode"].lower() or q in c["name"].lower()
            or (host and host == _host(c.get("website", "")))]


def get(code: str) -> dict | None:
    for c in COMPANIES:
        if c["asxCode"].lower() == code.lower():
            return c
    from . import store
    return store.get_company(code)


def label(company: dict) -> str:
    """How a company is named in emails and reports."""
    if company.get("listed", True):
        return f"{company['name']} (ASX: {company['asxCode']})"
    return f"{company['name']} (private company)"


def _host(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def normalise_website(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise CompanyError("Enter the company website")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    host = urlparse(url).hostname or ""
    if "." not in host or " " in url:
        raise CompanyError("That does not look like a website address")
    return url.rstrip("/")


def _code_for(host: str) -> str:
    base = re.sub(r"[^A-Z0-9]", "", host.split(".")[0].upper())[:8] or "PRIVATE"
    taken = {c["asxCode"] for c in all_companies()}
    code, n = base, 2
    while code in taken:
        code, n = f"{base[:7]}{n}", n + 1
    return code


def add_private(name: str, website: str, contact_email: str = "", sector: str = "",
                created_by: str | None = None, asx_code: str = "") -> dict:
    """Add a company that is not in the seed list: a private company, or a
    listed one if an ASX code is given. Returns the stored company, or the
    existing one if a company with the same website is already on file."""
    from . import store

    name = (name or "").strip()
    url = normalise_website(website)
    host = _host(url)
    existing = [c for c in all_companies() if _host(c.get("website", "")) == host]
    if existing:
        return existing[0]
    if not name:
        name = host.split(".")[0].replace("-", " ").title()
    contact = (contact_email or "").strip()
    if contact and not _EMAIL.match(contact):
        raise CompanyError("Enter a valid contact email, or leave it empty")
    code = (asx_code or "").strip().upper()
    if code:
        if not re.fullmatch(r"[A-Z0-9]{3,5}", code):
            raise CompanyError("An ASX code is 3 to 5 letters or numbers")
        if get(code):
            raise CompanyError(f"{code} is already on file")
    company = {"asxCode": code or _code_for(host), "name": name[:160], "website": url,
               "sector": sector.strip()[:80] or None, "tier": "ASX listed" if code else "Private",
               "listed": bool(code), "contactEmail": contact or None}
    return store.save_company(company, created_by=created_by)
