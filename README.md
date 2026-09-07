###ESG Governance Assessment Platform

Rates ASX listed companies against the ASX Corporate Governance Council
Principles and Recommendations, using free public sources only.

Built for Provision IT Pty Ltd. COMP30022 IT Project, University of Melbourne.

What it does
Enter an ASX code. The platform crawls that company's public website, finds
governance documents, extracts disclosures with a language model, scores them
with deterministic code, and reports the result so every finding traces back to
a quoted passage on a numbered page in a stored document.

###Three properties the design protects:

Two figures, never one. Transparency asks whether the company told us.
Practice asks whether they are doing it. They are never averaged.
Missing data is five states. Disclosed, explained departure, not
disclosed, not applicable, evidence gap. Conflating them is how bad ratings
happen.
Source quality never enters a score. It travels alongside as a separate
confidence letter.

###Layout
    backend/    FastAPI service: harvest, extract, read, score
    frontend/   Six screen interface, static, no build step

Running it
Two terminals.

    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env          # add your API key
    export $(grep -v '^#' .env | xargs)
    uvicorn app.main:app --reload --port 8080

    cd frontend
    python3 -m http.server 8000

Open http://localhost:8000/ and switch the toggle to live backend.

backend/fixture-site is a test environment with real PDFs, one missing
document and one path blocked by robots.txt, so the whole pipeline can run
with no internet.

Tests
    cd backend && python test_offline.py

Thirty one assertions, no network and no API key required. They cover the rules
the client agreed to.

Team
Agam Johal (lead), Chen Yu Lin, Pulitha Wimalendra, Jun Hyun Cho, Toan Le.
Client: Mick Both, Provision IT. Supervisor: Kian Dsouza.
