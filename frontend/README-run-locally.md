# Provision IT Governance Assessment - local demo

Five screens: Search, Retrieval, Assessment, Insufficient, History.
DisclosureGrid.dc.html is a component loaded by index.html at runtime. Keep it
in the same folder or the grid renders as an empty grey box.
Runs entirely offline. React, Babel and the three brand fonts are bundled
in ./vendor, so nothing is fetched from the internet at page load.

## Run it

Unzip, open a terminal in this folder, then:

    python3 -m http.server 8000

Open http://localhost:8000

That is the whole setup. Stop the server with Ctrl+C.

If port 8000 is taken, use another number: `python3 -m http.server 5173`

Node alternative, if you prefer:

    npx serve .

## It must be served over HTTP

Double-clicking index.html will show a blank page. scraper.js loads as an
ES module and browsers block module loading over file:// URLs. Always use
the local server above.

## Demo path

1. Search screen, type MFG or Meridian, press Enter
2. Retrieval plays the source log. Pause on the anti-bribery policy 404 and
   the scanned sustainability report, these are the two visible proofs that a
   retrieval failure is recorded rather than folded into a low score
3. Assessment shows the band, confidence letter, both scores, the disclosure
   grid and all eight principles with per criterion notation
4. Insufficient tab, Torrens Bay Holdings, the declined rating case
5. History tab, prior runs across two matrix versions

Other companies to search: KRM (Leading), YLT (Minimal), TBH (not rated).

Leave the "Live retrieval" toggle off. It performs a real cross origin fetch
through a reader proxy and needs internet. It is prototype keyword matching,
not the pipeline.

## Reset state

History is written to browser localStorage under `provisionit.history.v1`.
To start clean, open devtools, Application, Local Storage, and delete that key.

## Data

All data is hardcoded in index.html. Connecting it to the real API is separate
work, described in api-contract-v0.1.md.
