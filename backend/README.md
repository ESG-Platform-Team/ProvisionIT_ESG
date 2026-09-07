# Governance assessment backend

Harvests public governance documents from an ASX listed company's website,
extracts disclosures with Gemini, and scores them deterministically against the
ASX Corporate Governance Council principles.

Implements `api-contract-v0.1.md`, so the frontend switches from mock data to
this by changing one environment variable.

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your key in `.env`. Get one at https://aistudio.google.com/apikey.

`.env` is gitignored. Never commit a key, never paste one into a chat, a ticket
or a screenshot. If one leaks, revoke it in AI Studio rather than hoping.

```bash
export $(grep -v '^#' .env | xargs)
```

## Run one assessment

```bash
python run_cli.py --list          # seeded companies
python run_cli.py BEN             # full run with Gemini
python run_cli.py BEN --no-llm    # keyword extraction only, no API calls
python run_cli.py BEN --json out.json
```

## Run the API

```bash
uvicorn app.main:app --reload --port 8080
curl localhost:8080/api/health
curl "localhost:8080/api/companies?q=bendigo"
curl -X POST localhost:8080/api/assessments \
  -H 'Content-Type: application/json' -d '{"asxCode":"BEN"}'
```

Poll `GET /api/assessments/{runId}` until status is COMPLETE.

## Tests

```bash
python test_offline.py
```

Thirty-one assertions, no network, no API key, no cost. They cover the parts
that must not drift: the five disclosure statuses, an evidence gap never
becoming a maturity of zero, an explained departure counting toward
transparency only, declining to rate under thin coverage, and source quality
having no effect on any score.

That suite is only possible because scoring is deterministic. Worth saying at a
review, because it is the same property that makes a rating defensible.

## How a run works

1. **Discover.** Crawl the company site two levels deep, from the homepage to
   any governance or investor hub, and classify links that look like governance
   documents. Seventeen document types are recognised.
2. **Fetch.** Check robots.txt per host, wait 1.5 seconds between requests to
   the same host, identify the crawler honestly in the User-Agent. A disallowed
   URL produces a BLOCKED task with no document, which is a recorded finding.
3. **Extract.** pdfplumber for PDFs, falling back to pypdf, keeping text per
   page so evidence carries a page number. A PDF with no text layer is a scan,
   which routes to Tesseract if installed and is marked UNREADABLE if not.
4. **Window.** For each principle, pull passages around keyword hits with the
   page number attached, capped at 26,000 characters. This cuts the token bill
   and improves accuracy, because a model reading four relevant passages beats
   one skimming a 200 page annual report.
5. **Extract with Gemini.** One call per principle, eight per company, with a
   JSON schema and temperature zero. The model reports what it found with a
   verbatim excerpt and page. It does not decide a band.
6. **Score.** Pure code. Applies the matrix, the five-value disclosure enum, the
   band thresholds and the confidence letter. No model is called.

## Why one call per principle

The free tier runs Flash at roughly 10 to 15 requests per minute and around
1,500 per day, and the Pro models are no longer free. Eight calls assesses a
company in about a minute. One call per criterion would be thirty-one, four
times the quota for no meaningful gain.

Responses are cached on disk keyed by model, matrix version and prompt hash, so
re-running the same company costs nothing. This is the local stand-in for the
DynamoDB extraction cache on the architecture diagram.

## Before this touches a real client

Prompts sent on the Gemini free tier may be used by Google to improve their
models. Everything we send is already public governance material, so the
exposure is low, but it is Mick's call rather than ours. The paid tier removes
that clause. Worth raising in the weekly contact he asked for.

## What is not built yet

Deliberately out of scope for the MVP, and on the architecture diagram as the
deployment target:

- Queue and state machine. The pipeline runs synchronously in one background
  task. SQS, Step Functions and the scheduler stay as the target design.
- Persistence. Runs are held in memory. Raw documents are written to `data/raw`
  keyed by content hash, which is the MinIO and S3 shape, but there is no
  Postgres yet.
- Change detection. Content hashes are computed and stored, so the comparison
  is a small addition, but sequence diagram 6 is not implemented.
- Auth. No Cognito, no JWT. Do not expose this beyond localhost.

## Known limits, stated plainly

The seeded company websites are starting points and their structures change.
If discovery comes back thin for a company, add known document URLs to
`extraUrls` in `app/companies.py` rather than deepening the crawl.

The keyword fallback that runs without an API key finds topics, not practices.
Everything it returns is capped at STATED, which is why a `--no-llm` run
typically lands on MINIMAL. That is the fallback being honest rather than the
scoring being wrong.

The Gemini call path is written against the documented REST API but has not
been exercised against the live endpoint from this machine. Run
`python run_cli.py BEN` with a key as the first thing you do, and check the
excerpts are real verbatim spans from the source rather than paraphrase.
