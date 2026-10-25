ESG Assessment Platform

Rates ASX listed companies on governance, environmental and social
disclosure, using free public sources first. Governance follows the ASX
Corporate Governance Council Principles and Recommendations. Environmental
(AASB S2, GRI 300) and Social (Modern Slavery Act, WGEA, GRI 400, Privacy Act,
cyber security) are v0.1 drafts pending review.

Built for Provision IT Pty Ltd. COMP30022 IT Project, University of Melbourne.

What it does
Enter an ASX code. The platform crawls that company's public website, finds
governance documents, extracts disclosures with a language model, scores them
with deterministic code, and reports the result so every finding traces back to
a quoted passage on a numbered page in a stored document.

Every assessment is formed by software and says so: on screen, on every
finding and in the PDF report. No analyst reviews it before it is shown.

Reports are exported as PDF and can be emailed from the app. Where public
sources are silent, an analyst can email the company a list of what is missing
with a secure upload link. Anything supplied is marked "provided on request"
and graded below published documents. No reply by the due date means the item
is reported as insufficient information, never as a zero.

Three properties the design protects:

Two figures, never one. Transparency asks whether the company told us.
Practice asks whether they are doing it. They are never averaged.
Missing data is five states. Disclosed, explained departure, not
disclosed, not applicable, evidence gap. Conflating them is how bad ratings
happen.
Source quality never enters a score. It travels alongside as a separate
confidence letter.

Layout
    backend/    FastAPI service: harvest, extract, read, score
    frontend/   Six screen interface, static, no build step

Demo
    ./demo.sh --reset

Starts the fixture company, API and frontend in one go and opens
http://localhost:8001. DEMO.md is the showcase script.

Running it by hand
Three terminals.

    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env          # add your API key
    export $(grep -v '^#' .env | xargs)
    uvicorn app.main:app --reload --port 8080

    cd frontend
    python3 -m http.server 8001

    cd backend/fixture-site
    python3 -m http.server 8123

Open http://localhost:8001/ and search TST for the offline fixture company.

Everyone signs in first (JWT). The first time, create an account on the sign-in
screen. Data lives in a relational database: SQLite locally, PostgreSQL via
DATABASE_URL; the schema is in docs/database.md.

Email is off by default: messages are saved to backend/data/mail and nothing
leaves the machine. Set SMTP_HOST and the other SMTP_ variables in .env to
deliver, and PUBLIC_BASE_URL to an address companies can reach so the upload
link in a request works outside your laptop.

backend/fixture-site is a test environment with real PDFs, one missing
document and one path blocked by robots.txt, so the whole pipeline can run
with no internet.

Tests
    cd backend && python test_offline.py

140 assertions, no network and no API key required. They cover the rules the
client agreed to: scoring, the three pillars, the machine interpretation
statement, the PDF, safe email, and the disclosure request lifecycle.

Contributing
Read CONTRIBUTING.md before opening a pull request: branch naming, commit
messages, pull request expectations and review. CHANGELOG.md records every
change.

Team
Agam Johal (lead), Chen Yu Lin, Pulitha Wimalendra, Jun Hyun Cho, Toan Le.
Client: Mick Both, Provision IT. Supervisor: Kian Dsouza.
