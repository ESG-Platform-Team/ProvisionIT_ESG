# Running the frontend and backend together

Two servers, two terminal tabs. The frontend is static and the backend is the
API. They talk over CORS on localhost.

## Terminal 1, the backend

```bash
cd backend
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8080
```

Check it: `curl localhost:8080/api/health`

## Terminal 2, the frontend

```bash
cd governance-demo
python3 -m http.server 8000
```

Open http://localhost:8000

## Switching between demo data and the live backend

The toggle at the top right of the search screen is the switch.

**Seeded demo data** (default). The four fictional companies, MFG, KRM, YLT and
TBH, with hardcoded findings. Nothing touches the network. This is the state to
demo the design in, and the state to fall back to if anything goes wrong.

**Live backend on.** Typing a code and pressing Enter posts to
`/api/assessments`, polls until the run completes, and renders the real result
through the same screens. Try BEN, BHP, COL or TST.

If the backend is unreachable the page says so in a dialog rather than quietly
showing seeded data, because a demo that claims to be live while showing fixed
numbers is worse than one that stops and explains.

## Rehearsing with no internet

`fixture-site/` is a small fake company website with real multi-page PDFs, one
missing document and one path blocked by robots.txt. Serve it and the whole
pipeline runs with no external network at all:

```bash
cd backend/fixture-site && python3 -m http.server 8123
```

Then assess `TST`. Useful for practising the demo on bad wifi, and it is what
the integration path is tested against.

## Where the API base is configured

One line near the top of `index.html`:

```html
<script>window.PROVISION_API_BASE = "http://localhost:8080";</script>
```

Change it if you move the backend. If the backend runs on a different origin,
add that origin to `ALLOWED_ORIGINS` in the backend `.env` too.

## How the connection is actually made

Two files, and only two.

`backend.js` is the only part of the frontend that knows a backend exists. It
searches companies, starts a run, polls until complete, and maps source log
outcomes to the states the retrieval screen draws.

`assessFromApi()` inside `index.html` maps the contract response onto the exact
object shape the page already rendered. Every screen, meter, dot row and pill
consumes the same fields it always did.

That is the whole integration. No component was changed. If a screen renders
wrong with live data, the bug is almost certainly in `assessFromApi` rather
than anywhere else, which is a useful thing to know at 11pm.

## What is deliberately not wired up yet

The evidence drill down, the export path and the annotate or override action
still use demo behaviour. The backend has
`/api/assessments/{runId}/criteria/{code}/evidence` ready and `backend.js`
exposes `evidenceFor()`, so that one is a small addition rather than new work.
