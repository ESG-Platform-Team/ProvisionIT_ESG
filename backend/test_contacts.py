#!/usr/bin/env python3
"""Published contact finder: reads only the company's own site, returns only
addresses the company published, ranks role inboxes first, skips unsuitable ones."""

import asyncio
import functools
import http.server
import threading
from pathlib import Path

from testkit import check, done, section

from app import contacts

site = Path(__file__).parent / "fixture-site"
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
handler.log_message = lambda *a: None
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_address[1]}"

section("FINDING PUBLISHED CONTACTS")
found = asyncio.run(contacts.find(url))
emails = [c["email"] for c in found["contacts"]]
roles = {c["email"]: c["role"] for c in found["contacts"]}
check("the sustainability inbox is found and ranked first", emails[0] == "sustainability@fixture-test.example")
check("an address written as [at] is understood", "sustainability@fixture-test.example" in emails)
check("mailto links are read without their subject", "company.secretary@fixture-test.example" in emails)
check("roles are labelled", roles.get("investor.relations@fixture-test.example") == "Investor relations"
      and roles.get("privacy@fixture-test.example") == "Privacy officer")
check("contacts on linked pages are found", any("privacy-policy" in c["source"] for c in found["contacts"]))
check("careers and similar inboxes are left out", "careers@fixture-test.example" not in emails)
check("image file names are not mistaken for addresses", not any(e.endswith(".png") for e in emails))
check("each address says which page it came from", all(c["source"].startswith(url) for c in found["contacts"]))
check("only a handful of pages are read", found["pagesChecked"] <= contacts.MAX_PAGES)

section("ROLES")
check("a personal-looking address is labelled as such",
      contacts._role("jane.citizen")[0] == "May be a personal address")
check("esg@ is a sustainability inbox", contacts._role("esg")[0] == "Sustainability")

server.shutdown()
done()
