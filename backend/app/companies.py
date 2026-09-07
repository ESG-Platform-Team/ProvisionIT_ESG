"""
Mick's confirmed test companies, plus room for the tougher targets he said would
come later.

These are starting points for discovery, not a hardcoded document list. The
harvester crawls the website and finds whatever governance material is actually
published, which is the behaviour we need to demonstrate. extraUrls exists for
the case where a document is published but not linked from anywhere the shallow
crawl reaches.
"""

COMPANIES = [
    # Offline fixture. Serve fixture-site on port 8123 and this runs the whole
    # pipeline with no internet at all, which is how to rehearse a demo on
    # unreliable wifi and how the integration test runs.
    {"asxCode": "TST", "name": "Fixture Test Group", "sector": "Test",
     "tier": "Fixture", "website": "http://localhost:8123", "extraUrls": []},
    {"asxCode": "BHP", "name": "BHP Group", "sector": "Materials",
     "tier": "ASX 20", "website": "https://www.bhp.com", "extraUrls": []},
    {"asxCode": "FMG", "name": "Fortescue", "sector": "Materials",
     "tier": "ASX 50", "website": "https://www.fortescue.com", "extraUrls": []},
    {"asxCode": "COL", "name": "Coles Group", "sector": "Consumer Staples",
     "tier": "ASX 50", "website": "https://www.colesgroup.com.au", "extraUrls": []},
    {"asxCode": "WOW", "name": "Woolworths Group", "sector": "Consumer Staples",
     "tier": "ASX 50", "website": "https://www.woolworthsgroup.com.au", "extraUrls": []},
    {"asxCode": "CBA", "name": "Commonwealth Bank of Australia", "sector": "Financials",
     "tier": "ASX 20", "website": "https://www.commbank.com.au", "extraUrls": []},
    {"asxCode": "NAB", "name": "National Australia Bank", "sector": "Financials",
     "tier": "ASX 20", "website": "https://www.nab.com.au", "extraUrls": []},
    {"asxCode": "BEN", "name": "Bendigo and Adelaide Bank", "sector": "Financials",
     "tier": "ASX 200", "website": "https://www.bendigoadelaide.com.au", "extraUrls": []},
]


def find(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    exact = [c for c in COMPANIES if c["asxCode"].lower() == q]
    if exact:
        return exact
    return [c for c in COMPANIES
            if q in c["asxCode"].lower() or q in c["name"].lower()]


def get(asx_code: str) -> dict | None:
    for c in COMPANIES:
        if c["asxCode"].lower() == asx_code.lower():
            return c
    return None
