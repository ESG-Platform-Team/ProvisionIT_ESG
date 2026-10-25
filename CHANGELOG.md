# Changelog

Every notable change, newest first. Each pull request adds a line under
Unreleased. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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

## [0.1.0] - 2026-09-07

### Added
- Governance assessment against the ASX Corporate Governance Council Principles
  (4th edition): harvest, extract, Gemini reading, deterministic scoring
- FastAPI service implementing api-contract v0.1 and the six-screen interface
- Offline fixture company and 31 offline tests
