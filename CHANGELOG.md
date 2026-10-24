# Changelog

Every notable change, newest first. Each pull request adds a line under
Unreleased. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- PostHog for user acceptance testing: page views, autocapture, session replay with inputs and
  email addresses masked, named events for the search-to-report funnel, and in-app surveys. Off
  until a key is set in frontend/analytics.config.js; vendored posthog-js 1.435.5; never loads on
  the company response page. Setup in docs/analytics.md (feature/posthog-uat)
- Fast demo modes: ./demo.sh --warm records Gemini's answers for TST, --replay serves them from
  the cache with no API calls, --film paces the source log for screen recording
  (feature/demo-speed)

### Changed
- No politeness pause between fetches from our own machine (localhost fixture); real websites
  keep the 1.5 s delay, now configurable with HARVEST_HOST_DELAY (feature/demo-speed)
- Cloudflare deployment: one Worker serves the website and forwards /api and /respond to the
  API running as a Cloudflare Container (backend/Dockerfile). Steps in DEPLOY.md
  (feature/cloudflare-deploy)
- PostgreSQL ready: connection strings from Neon, Supabase or RDS work unchanged (psycopg 3),
  with stale-connection checks (feature/cloudflare-deploy)
- Files companies upload are stored in the database as well as on disk, and restored when the
  disk copy is gone, because cloud container disks are wiped on restart
  (feature/cloudflare-deploy)

- View what a company sent back: each sent request in the Requests tab expands to show the
  documents provided (open in a new tab or download), who sent them, what was asked for and the
  timeline. Documents are served only to signed-in users and only from the responses folder
  (feature/request-composer)
- Find published contacts: reads the company's own contact, investor, sustainability and privacy
  pages (respecting robots.txt) and lists the addresses it publishes, role inboxes first, with the
  page each came from. Nothing is guessed, stored or sent automatically (feature/request-composer)
- Request composer can search companies on file or add a new one (private, or listed by ASX
  code) without leaving the form or running an assessment first (feature/request-composer)
- Request composer in the Requests tab: pick any company, choose ESG documents from a checklist
  grouped by pillar, add written-in items, a personal note and a due date, optionally include the
  criteria the latest assessment could not answer, and see the exact email update live before
  sending. Request emails now have an HTML version with an upload button (feature/request-composer)
- Add an ASX-listed company that is not on file by giving its ASX code (feature/private-companies)
- Private companies: add any company by website and contact email; it is stored, appears in
  search and the companies-on-file list, is assessed the same way, and is labelled as a private
  company (not an ASX code) in reports and request emails (feature/private-companies)
- Show / hide password on the sign-in form (feature/auth-sign-in)
- Sign in with JWT: HS256 tokens with issuer, audience, expiry and a unique id, revoked on
  sign-out; salted PBKDF2 password hashes; every API route except health and sign-in needs a
  token; reports and requests record who sent them and replies go to that person
  (feature/auth-sign-in)
- Relational database (SQLAlchemy): users, companies, assessment runs, pillar results, source
  documents, disclosure requests with their items and documents, an email log and revoked
  tokens, with foreign keys. SQLite locally, PostgreSQL via DATABASE_URL. Older databases are
  imported automatically. Schema in docs/database.md (feature/auth-sign-in)
- Interface: pillar selection and tabs, machine interpretation banner, PDF download,
  email and request panels, Requests screen, live progress (feature/frontend-esg-
  pillars)
- Live mode shows only real data: History lists stored runs, the Insufficient screen
  lists the criteria public sources did not answer, and illustrative peer dots are
  hidden on real runs (feature/frontend-esg-pillars)
- demo.sh starts the fixture company, API and frontend in one command; DEMO.md is the
  showcase script (feature/frontend-esg-pillars)
- Disclosure requests: email a company the criteria public sources did not answer, with
  a due date, secure upload link and opt-out (feature/disclosure-requests)
- Company response page; documents provided are re-assessed and graded C; a decline or
  no reply is reported as insufficient information, never a zero (feature/disclosure-
  requests)
- PDF report: every pillar, quoted evidence with page numbers, source log, method notes
  (feature/pdf-report-email)
- Email the report with the JSON result attached; without SMTP settings every message is
  saved to data/mail and nothing is sent (feature/pdf-report-email)
- Report email has an HTML layout with a pillar summary table; plain text stays the
  fallback (feature/pdf-report-email)
- One crawl assesses any combination of Governance, Environmental and Social
  (feature/multi-pillar-pipeline)
- Machine interpretation statement on every run and every finding, as the client asked
  (feature/multi-pillar-pipeline)
- Runs stored in SQLite; GET /api/assessments lists history (feature/multi-pillar-
  pipeline)
- Gemini model gemini-3.6-flash with fallback models (feature/multi-pillar-pipeline)
- Crawler recognises climate statements, modern slavery statements, WGEA reports,
  reconciliation action plans and privacy, environmental and supplier policies
  (feature/esg-document-crawler)
- Only the newest edition of each dated report is fetched (feature/esg-document-crawler)
- Fixture company gains a sustainability hub, climate statement, modern slavery
  statement, privacy policy and one broken link (feature/esg-document-crawler)
- Environmental matrix E-draft v0.1, 16 criteria, AASB S2 and GRI 300, pending review
  (feature/esg-pillar-matrices)
- Social matrix S-draft v0.1, 14 criteria, including data privacy and cyber security,
  pending review (feature/esg-pillar-matrices)
- Pillar registry; the scoring engine scores any pillar's matrix; source grades for
  climate, modern slavery, WGEA and policy documents, and grade C for documents provided
  on request (feature/esg-pillar-matrices)
- Coding standards in CONTRIBUTING.md: branch naming, Conventional Commits, pull request
  expectations and peer review (docs/coding-standards)
- Pull request template and a CI workflow that lints and runs every offline test on pull
  requests to integration and main (docs/coding-standards)
- backend/ruff.toml and backend/testkit.py so lint and tests are the same for everyone
  (docs/coding-standards)

### Changed
- The website finds the API on its own domain when deployed and on localhost:8080 for the local
  demo; request email links use the address the analyst is on unless PUBLIC_BASE_URL is set
  (feature/cloudflare-deploy)

## [0.1.0] - 2026-09-07

### Added
- Governance assessment against the ASX Corporate Governance Council Principles
  (4th edition): harvest, extract, Gemini reading, deterministic scoring
- FastAPI service implementing api-contract v0.1 and the six-screen interface
- Offline fixture company and 31 offline tests
