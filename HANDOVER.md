# Handover: ESG Assessment Platform

Handed over to **Provision IT Pty Ltd** on **2 November 2026** by the COMP30022
IT Project team, University of Melbourne. This file is the starting point for
anyone who runs, changes or deploys the platform after the semester.

| | |
|---|---|
| Live demo | https://provisionit-esg.provisionit-esg.workers.dev (sign-in required) |
| Code | This repository. Release **v1.3.0** is the handover release |
| Project documentation | [Confluence space](https://provisionitesg.atlassian.net/wiki/spaces/PEP), with a [Handover page](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/18612227) linking here |
| Task history | [Jira board](https://provisionitesg.atlassian.net/jira/software/projects/ESG/boards/2) |
| Owner | Provision IT Pty Ltd ([LICENSE](LICENSE)) |
| Support | Agam Johal, free maintenance until **2 May 2027** ([section 15](#15-maintenance-and-contact)) |
| Team | Agam Johal (lead), Chen Yu Lin, Pulitha Wimalendra, Jun Hyun Cho, Toan Le |
| Client | Mick Both, with Chris (CEO) and Adam, Provision IT |
| Supervisor | Kian Dsouza |

## Contents

1. [TL;DR](#1-tldr)
2. [Project overview](#2-project-overview)
3. [Features delivered, by sprint](#3-features-delivered-by-sprint)
4. [System requirements](#4-system-requirements)
5. [Run it on your laptop](#5-run-it-on-your-laptop)
6. [Accounts, API keys and credentials](#6-accounts-api-keys-and-credentials)
7. [Deploying](#7-deploying)
8. [Starting up and shutting down](#8-starting-up-and-shutting-down)
9. [Architecture, layers and key modules](#9-architecture-layers-and-key-modules)
10. [Key algorithms](#10-key-algorithms)
11. [Database and data](#11-database-and-data)
12. [Design system and fonts](#12-design-system-and-fonts)
13. [User manual](#13-user-manual)
14. [Outstanding items and future development](#14-outstanding-items-and-future-development)
15. [Maintenance and contact](#15-maintenance-and-contact)
16. [Documentation index and traceability](#16-documentation-index-and-traceability)
17. [Changelog and licence](#17-changelog-and-licence)

## 1. TL;DR

- **See it working:** open the live demo, create an account, search `TST`.
- **Run it locally:** `./demo.sh --reset` (needs Python 3.11+). Opens
  http://localhost:8001. Nothing leaves the laptop.
- **Make it yours:** add your own Gemini key, database and email account
  ([section 6](#6-accounts-api-keys-and-credentials)). The team's keys are
  removed at handover.
- **Host it yourselves:** Cloudflare in about 20 minutes ([DEPLOY.md](DEPLOY.md)),
  or AWS in about half a day ([docs/deploy-aws.md](docs/deploy-aws.md)).
- **Change it safely:** every pull request runs 346+ automated checks, browser
  tests and a secret scan ([CONTRIBUTING.md](CONTRIBUTING.md)).

## 2. Project overview

The platform rates ASX-listed and private companies on **Governance,
Environmental and Social** disclosure, using free public sources. Governance
follows the ASX Corporate Governance Council Principles and Recommendations
(4th edition). Environmental (AASB S2, GRI 300) and Social (Modern Slavery
Act, WGEA, GRI 400, Privacy Act, cyber security) are v0.1 drafts awaiting
Provision IT's review.

An analyst enters a company. The platform crawls its website, finds its
governance and sustainability documents, has a language model quote the
relevant passages, scores them with deterministic code, and shows the result
so that **every finding traces to a quoted passage on a numbered page**.

The rules the client set, which the design protects:

- **Reported, not interpreted.** Every assessment says it was formed by
  software. The model only quotes; code scores.
- **Two figures, never one.** Transparency (did they tell us?) and Practice
  (are they doing it?) are never averaged.
- **Missing data has five states:** disclosed, explained departure, not
  disclosed, not applicable, evidence gap. None of them becomes a zero.
- **Source quality never enters a score.** It travels beside it as a
  confidence letter (A to E).
- **Decline to rate** when less than 55% of criteria can be reached.

## 3. Features delivered, by sprint

User story IDs match the [User story page](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/2261033)
and `backend/test_acceptance.py`.

**Sprint 1 (10 Aug to 6 Sep): Governance end to end**

- Resolve a company by name or ASX code to one legal entity (US-04, ESG-2)
- Gather only from free public sources, respecting robots.txt (US-05, ESG-7)
- Record every retrieval as retrieved, failed or unreadable (US-06, ESG-8)
- Governance matrix on the ASX Principles, the same for every company (US-12,
  ESG-4)
- Language model extraction approach (ESG-22), Figma flow and admin mock-ups
  (ESG-6, ESG-9)

**Sprint 2 (6 Sep to 26 Oct): the hosted ESG MVP, release v1.2.0**

- Maturity scale, five missing-data states, Transparency and Practice kept
  separate, insufficient evidence shown, matrix version recorded (US-07 to
  US-13)
- Source confidence separate from the score; every claim linked to its quoted
  passage and page (US-14 to US-17)
- Environmental (16 criteria) and Social (14 criteria) draft matrices assessed
  in the same run as Governance; machine-interpretation statement (US-24 to
  US-28)
- PDF report, JSON export and email delivery (US-19, US-20, US-29, US-30)
- Disclosure requests with a secure upload page; company material marked
  "provided on request"; no reply is never a zero (US-31 to US-34)
- Sign-in, relational database, history kept by date and framework version
  (US-21 to US-23, US-35, US-36)
- Private companies, request composer, published-contacts finder (US-37)
- PostHog for user acceptance testing, fast demo modes
- Cloudflare hosting with PostgreSQL; CI on every pull request; continuous
  deployment with an approval gate and a smoke test

**Sprint 3 (26 Oct to 9 Nov): prove and hand over, release v1.3.0**

- Handover meeting with Mick and Chris, 2 November
  ([minutes](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/18415618))
- Defects from the 25 October test run fixed (see [CHANGELOG.md](CHANGELOG.md))
- This handover pack, AWS deployment guide and workflow, licence transfer

## 4. System requirements

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.11 or 3.12 | The API (CI uses 3.11, the container 3.12) |
| A modern browser | Chrome, Edge, Safari or Firefox, current | The interface |
| Docker Desktop | 4.x | Building the API image (Cloudflare and AWS) |
| Node.js | 22 or later | Wrangler (Cloudflare) and the browser tests |
| PostgreSQL | 14 or later | Production database (SQLite is used locally) |
| Git | any recent | |

Python packages are pinned by minimum version in `backend/requirements.txt`;
the versions tested at handover are in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
The frontend has **no build step**: React, Babel and the fonts are vendored in
`frontend/vendor/`, so it runs offline.

## 5. Run it on your laptop

```bash
git clone <this repository>
cd provisionit_esg
./demo.sh --reset
```

`demo.sh` creates `backend/.venv`, installs the requirements, and starts
three things: the offline test company **TST** (port 8123), the API (8080) and
the website (8001). It opens http://localhost:8001. The first time, click
**Create an account**. `Ctrl-C` stops everything.

| Command | What it does |
|---|---|
| `./demo.sh --reset` | Fresh local database, keyword matching, fully offline |
| `./demo.sh --reset --live` | Also loads `backend/.env`, so your Gemini key and SMTP are used |
| `./demo.sh --warm` then `--reset --replay` | Records Gemini's answers for TST once, then replays them with no API calls |

To run the parts by hand, or on Windows without a Bash shell, see
[README.md](README.md#running-it-by-hand). To set your keys locally:

```bash
cp backend/.env.example backend/.env    # then fill in the values (section 6)
```

`backend/.env` is ignored by git, and CI fails if a key is ever committed.

## 6. Accounts, API keys and credentials

**The team's keys and accounts are removed at handover.** The code holds no
credentials: every key is read from the environment. Create your own as below
and set them in `backend/.env` (local), as Cloudflare secrets, or as AWS
Secrets Manager secrets.

| Setting | What it is | How to get your own | Required? |
|---|---|---|---|
| `GEMINI_API_KEY` | Google Gemini language model | https://aistudio.google.com/apikey, signed in with a Provision IT Google account. Use a paid tier for confidential work: the free tier may use prompts to train Google's models | Optional. Without it the platform uses keyword matching and labels runs as such |
| `GEMINI_MODEL` | Model name | Default `gemini-3.6-flash`; `GEMINI_FALLBACK_MODELS` is tried if Google withdraws it | Optional |
| `DATABASE_URL` | PostgreSQL connection string | Neon (free tier), Amazon RDS or Supabase | Production only. Empty means SQLite locally |
| `JWT_SECRET` | Signs sign-in tokens | `openssl rand -base64 48`. Changing it signs everyone out | Production. Generated automatically locally |
| `SIGNUP_DOMAINS` | Who may create an account | e.g. `provisionit.com.au` | **Set it in production**, otherwise anyone with the URL can sign up |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Outgoing email | Amazon SES SMTP credentials, Microsoft 365, or a Gmail app password | Optional. Without it every email is saved in the app, not sent |
| `PUBLIC_BASE_URL` | Address in request emails | Your site's address | Only behind a custom domain |
| PostHog key | Usage analytics for testing | https://posthog.com, then `frontend/analytics.config.js` | Optional, off by default |

**Hosting and repository accounts**

| Account | Today | Action for Provision IT |
|---|---|---|
| GitHub repository | Transferred to Provision IT at handover | Make it private; add your developers; keep branch protection on `main` |
| GitHub Actions secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | Team's values removed | Add yours if you deploy to Cloudflare ([DEPLOY.md](DEPLOY.md)) |
| GitHub environment `production` | Required reviewer was Agam | Set your own reviewer: Settings > Environments > production |
| Cloudflare (live demo) | Team's account, kept running during the maintenance period | Deploy to your own account when ready; the team's demo is then switched off |
| Neon database (live demo) | Team's account | Your own database; the team's is deleted with the demo |
| Gmail SMTP (live demo) | Team's mailbox, removed at handover | Your own SMTP or SES |

**Test logins and dummy data.** There are no shared or default accounts. Each
person creates their own on the sign-in screen (password 10+ characters). The
only dummy data is the fictional company **TST**, described in
[section 11](#11-database-and-data).

## 7. Deploying

| Target | Guide | Effort | Cost (about) |
|---|---|---|---|
| Cloudflare Workers + Containers, Neon PostgreSQL (what runs today) | [DEPLOY.md](DEPLOY.md) | 20 minutes | US$5 a month |
| AWS: CloudFront, S3, ALB, ECS Fargate, RDS, Secrets Manager | [docs/deploy-aws.md](docs/deploy-aws.md) | Half a day | US$60 to 65 a month |
| AWS target design: SQS worker, S3 uploads, Cognito, SES, Bedrock | [docs/deploy-aws.md, Stage 2](docs/deploy-aws.md#stage-2-the-target-design) and Confluence *AWS deployment architecture* | Code changes | About US$95 a month |

**Continuous deployment.** `.github/workflows/ci.yml` runs on every pull
request. `.github/workflows/deploy.yml` deploys to Cloudflare after CI passes on
`main` and a named reviewer approves, then runs `scripts/smoke_test.sh` against
the live site. `.github/workflows/deploy-aws.yml` does the same for AWS once
your AWS account is connected (OpenID Connect, no stored keys).

**Rolling back.** Cloudflare: `cd cloudflare && npx wrangler rollback`. AWS:
previous ECS task definition revision. Both are explained in the guides.

## 8. Starting up and shutting down

| Where | Start | Stop | Check |
|---|---|---|---|
| Laptop | `./demo.sh` | `Ctrl-C` in that terminal | http://localhost:8080/api/health |
| Cloudflare | Always on. The API sleeps after 30 idle minutes and wakes on the next request (a few seconds; open the site a minute before a demo) | Workers & Pages > provisionit-esg > Settings > Delete, or deploy a maintenance page | `https://<site>/api/health` |
| AWS | ECS service desired count 1 | Desired count 0 (RDS keeps the data; stop RDS too to save cost, up to 7 days) | `https://<site>/api/health` |

`/api/health` should return `"status": "ok"` and `"authRequired": true`, plus
`"llmConfigured"` and `"smtpConfigured"` showing whether your keys are set.

## 9. Architecture, layers and key modules

```
Browser
  |
  v
Edge (Cloudflare Worker today, CloudFront on AWS)
  |-- /api/*, /respond/*  ->  API container (FastAPI, backend/Dockerfile)
  |                              harvest -> extract -> read -> score -> report
  |                              store  ->  PostgreSQL (SQLite locally)
  '-- everything else    ->  website files (frontend/, static, no build step)
```

The frontend and backend meet at a frozen JSON contract
([frontend/CONNECTING.md](frontend/CONNECTING.md)), which is why either side can
change without breaking the other.

**Backend layers (`backend/app/`)**, where to look when changing something:

| Layer | Module | Responsibility |
|---|---|---|
| HTTP | `main.py` | Every API route, sign-in checks, file upload limits |
| Orchestration | `pipeline.py` | Runs an assessment: harvest, extract, read, score, assemble. Holds live progress (`RunState`) |
| 1. Harvest | `harvest.py` | Crawls the company site, obeys robots.txt, picks the newest edition of each document |
| 2. Extract | `textract.py` | Page-numbered text from PDF and HTML (pdfplumber, pypdf) |
| 3. Read | `llm.py` | Gemini prompt per principle, fixed JSON schema, temperature 0, prompt-hash cache; keyword fallback |
| 4. Score | `scoring.py` | Deterministic scoring. **No model is ever called here** |
| Criteria | `matrix.py`, `matrix_environmental.py`, `matrix_social.py`, `pillars.py` | The three versioned matrices and the pillar registry |
| Output | `report.py`, `mailer.py` | PDF report (ReportLab), email over SMTP or a saved outbox |
| Requests | `disclosure.py`, `contacts.py` | Disclosure requests, company response page, published-contacts finder |
| Data | `db.py`, `store.py`, `companies.py` | SQLAlchemy schema, persistence, company register |
| Security | `auth.py` | Accounts, PBKDF2 passwords, JWT issue, check and revoke |

**Frontend (`frontend/`)**

| File | Responsibility |
|---|---|
| `index.html` | The six screens and all interface logic (React, inline styles) |
| `backend.js` | The only file that calls the API |
| `scraper.js` | Seeded demo data used when the backend is off |
| `support.js` | Formatting and shared helpers |
| `analytics.js`, `analytics.config.js` | PostHog (off until a key is set) |
| `vendor/` | React, Babel, posthog-js and fonts, so the site works offline |

Architecture diagrams, use case and sequence diagrams are on Confluence:
[Architecture Diagrams](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/3768381),
[As-built architecture](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/16351289),
[AWS deployment architecture](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/13041670).

## 10. Key algorithms

**Scoring (`scoring.py`).** For each criterion the model (or keyword matcher)
proposes a status and a maturity level from 0 to 4 (absent, stated,
implemented, monitored, embedded), with a quote and a page. The code then:

1. Drops any criterion not in scope for the company (not applicable).
2. Computes **Practice** as the weighted mean maturity across in-scope
   criteria with evidence, and maps it to a band: 3.4 Leading, 2.2
   Established, 1.4 Developing, 0.5 Minimal, below that Not evidenced.
3. Computes **Transparency** separately: disclosed or explained departures
   count; an explained departure is transparency, not practice.
4. Grades sources A to E by document type (audited annual report A, company
   policy B, website text C, provided on request C) and reports the
   **confidence letter** beside the band. It never changes the band.
5. **Declines to rate** if fewer than 55% of in-scope criteria could be
   reached, and says why.

**Weighting.** Every criterion has a `weight` in its matrix file (all 1.0
today). The Practice mean is weighted, so changing a number in
`matrix*.py` changes how much that criterion counts. This is where the
context-based weighting Mick and Chris asked about plugs in (see
[section 14](#14-outstanding-items-and-future-development)).

**Choosing documents (`harvest.py`).** Starts at the company website, follows
links whose text or address suggests governance, sustainability, climate,
modern slavery or policies, checks robots.txt before every fetch, waits 1.5
seconds between requests to a real site, and keeps only the newest edition of
each document type.

**Reading (`llm.py`).** One call per principle (eight for Governance), with
only the passages that match the principle's keywords. The model must answer
in a fixed JSON schema with a verbatim quote and page. Answers are cached by
prompt hash, so a re-run costs nothing.

**Importing from third parties.** There is no paid data feed. Data comes from
(a) the company's own public website and PDFs, and (b) documents a company
uploads through a disclosure request, which are stored with the provenance
"provided on request" and graded C.

## 11. Database and data

Schema, with an entity relationship diagram: [docs/database.md](docs/database.md).
Ten tables: `users`, `revoked_tokens`, `companies`, `assessment_runs`,
`pillar_results`, `source_documents`, `disclosure_requests`, `request_items`,
`request_documents`, `email_log`. The API creates them on first start.

| Where | Database | Access |
|---|---|---|
| Laptop | SQLite at `backend/data/platform.db` | Any SQLite browser. Delete the file (or `./demo.sh --reset`) to start again |
| Cloudflare | Neon PostgreSQL | Your own `DATABASE_URL` once you deploy; `psql "$DATABASE_URL"` |
| AWS | RDS PostgreSQL in a private subnet | From inside the VPC, credentials in Secrets Manager |

**Data in the system at handover**

| Data | Real or test | Notes |
|---|---|---|
| **TST, "Fixture Test Group"** | **Fictional test company** | `backend/fixture-site/`: a small website with six real PDFs, one deliberately broken link and one path blocked by robots.txt. Runs inside the API, so the demo works offline and in the cloud |
| Company register | Real public information | ASX codes, names and websites of listed companies |
| Assessment runs on the live demo | Team testing | Removed with the team's demo database |
| User accounts on the live demo | Team members | Removed with the team's demo database |
| Emails | None sent to real companies | Every request so far used team addresses as the "company" contact |

Do not send requests to real company addresses until outreach has been checked
against the Spam Act 2003.

## 12. Design system and fonts

Mick and Chris were happy with the design. The interface follows Provision
IT's brand: a dark ink canvas, amber accent, and three typefaces.

**Colour**

| Token | Hex | Use |
|---|---|---|
| Ink | `#0E0F14` | Page background, primary text on light cards |
| Amber | `#F4BF3F` | Brand accent, primary buttons, focus, active tab |
| Amber deep | `#8A6A12` | Amber text on light backgrounds (meets contrast) |
| Amber soft | `#FDF3D8` | Highlight fills, the machine-interpretation banner |
| Paper | `#F4F5F7` | Light text on ink, card backgrounds |
| Line | `#DCDEE4` | Borders and dividers |
| Mute | `#8A8F9C` | Secondary text, labels |
| Mid | `#4A4E5C` | Body text on light cards |
| Panel | `#2E323F` | Raised surfaces on ink |
| Alert | `#E5484D` | Errors and failed retrievals |

**Type**

| Typeface | Weights | Use |
|---|---|---|
| Archivo | 600, 700, 800 | Headings, uppercase display titles, scores |
| Inter | 400, 500, 600 | Body text and inputs |
| IBM Plex Mono | 400, 500 | Labels, ASX codes, tabs, the source log, figures |

All three are under the SIL Open Font License and are self-hosted in
`frontend/vendor/fonts/`, so nothing loads from Google.

**Changing a font**

1. Download the `.woff2` files for the new font (for example from
   [Fontsource](https://fontsource.org), which serves the same files used now)
   into `frontend/vendor/fonts/`.
2. Edit `frontend/vendor/fonts.css`: one `@font-face` block per weight, with
   the new family name and file.
3. Replace the family name in `frontend/index.html`,
   `frontend/DisclosureGrid.dc.html` and `frontend/support.js`. Styles are
   inline, so a find and replace of, say, `'IBM Plex Mono'` covers every
   screen.
4. For the PDF report, put `.ttf` files in `backend/app/fonts/` and update the
   file names in `_fonts()` in `backend/app/report.py`. If a file is missing,
   the PDF falls back to Helvetica rather than failing.
5. Check the screens at http://localhost:8001 and download a PDF report.

**Changing a colour.** The same hex values appear in `frontend/index.html`
(inline styles), `backend/app/report.py` (top of file, for the PDF) and
`backend/app/disclosure.py` and `main.py` (email and response-page HTML). A
find and replace of the hex value across those files changes it everywhere.

## 13. User manual

The walk-through for each use case, written as a script you can follow, is in
[DEMO.md](DEMO.md). The acceptance tests in `backend/test_acceptance.py`
describe each story's expected behaviour as Given / When / Then. In short:

1. **Sign in.** Create an account with your work email the first time.
2. **Assess a company.** Type an ASX code (e.g. `BEN`) or a name, choose the
   pillars, press Enter. The retrieval screen lists every document as it is
   fetched, including failures.
3. **Read the scorecard.** Each pillar shows Practice and Transparency bands
   and a confidence letter. Open a criterion to see the quoted passage and its
   page.
4. **Not rated?** The Insufficient screen lists which criteria public sources
   did not answer.
5. **Share it.** Download the PDF, or email it from the app.
6. **Ask the company.** *Request missing disclosures* emails the company a list
   with a secure upload link and a due date. Responses appear under
   **Requests** and can be re-assessed.
7. **Add a private company.** Search, then *Add company* with its website and
   contact email.
8. **History** lists every past run, reproducible exactly as issued.

## 14. Outstanding items and future development

**Not completed this semester**, with the reason and a suggested next step.
All have Jira tickets.

| Item | Ticket | Why not done | Suggested next step |
|---|---|---|---|
| Client review of the Environmental and Social criteria | ESG-50 | Needs Provision IT's review of the v0.1 drafts | Mick reviews the two matrix files; the team removes the draft labels |
| Validation against independent human scoring | ESG-19 | Second rater still reviewing (Coles Group, 31 criteria) | Finish the comparison on Confluence, then tune thresholds if needed |
| Grade for policy pages published as HTML | ESG-62 | A judgement call: B by document type, or C as website text | Provision IT decides; it is one line in `SOURCE_GRADES` |
| Open the quoted passage on screen from a finding | ESG-51 | Time | Evidence endpoint exists (`/criteria/{code}/evidence`); needs a viewer |
| Scheduled check for overdue requests | ESG-57 | Needs a scheduler | Cloudflare Cron Trigger or AWS EventBridge calling one endpoint |
| Run more than one API instance | | Progress held in memory | Move progress into the database ([AWS guide, Stage 2](docs/deploy-aws.md#stage-2-the-target-design)) |

**Raised by Mick and Chris at handover**

- **Beyond ESG.** Criteria live in matrix modules registered in `pillars.py`.
  A new domain is a new `matrix_<name>.py` (criteria, keywords, weights), a
  document checklist in `disclosure.py`, and a line in the pillar registry. The
  harvest, read, score, report and request pipeline is reused unchanged.
- **Context-based weighting** (for example an insurance claim counting more
  for a cancer patient). The scoring engine already uses a per-criterion
  weight. The next step is a small rules table, "when the case is X, criterion
  Y weighs Z", applied by deterministic code before scoring. Weights stay
  versioned with the matrix, so every past result remains reproducible.
- **Pricing.** Running costs are in [section 7](#7-deploying). Variable cost
  per assessment is mainly the language model (about eight calls per pillar,
  cached on re-runs), so per-assessment or per-seat subscription pricing both
  fit.
- **Joining with the ticketing system (team T4-1).** A disclosure request can
  raise a ticket in Provision IT's ticketing application, so its progress is
  tracked there and both sides get email notifications as it moves (ESG-63).
  The request lifecycle (sent, responded, declined, no response) already maps
  to ticket states.

**Known limitations**

- Scanned PDFs with no text layer are skipped (Textract on AWS would add OCR).
- The Gemini free tier may use prompts for training; use a paid tier or Bedrock
  for confidential documents.
- Email from Cloudflare Containers may be blocked on SMTP ports; an HTTP email
  API (SES, Resend) is the fix, noted in [DEPLOY.md](DEPLOY.md).

## 15. Maintenance and contact

Agam Johal provides **six months of free maintenance**, from **2 November 2026
to 2 May 2027**, covering:

- fixing defects in the delivered features
- security and dependency updates
- help deploying to Provision IT's own Cloudflare or AWS account
- questions about the code, the design or the documentation

New features (such as a new assessment domain or the ticketing integration) are
outside free maintenance and can be scoped separately.

| | |
|---|---|
| Name | Agam Johal, team lead |
| Phone | +61 416 319 294 |
| Email | agam.johal@gmail.com |

These contact details remain valid after the maintenance period.

To report a problem, email with what you did, what you expected and what
happened, plus the run ID from the History screen if there is one.

## 16. Documentation index and traceability

All on [Confluence](https://provisionitesg.atlassian.net/wiki/spaces/PEP). The
**traceability matrix** is the
[User story page](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/2261033):
each row links requirement (FR) to story, Jira ticket and acceptance test.

| Area | Pages |
|---|---|
| Requirements | [Project Requirements](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/229489), [User stories and traceability](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/2261033), [Personas](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/3768327), [Motivation Model](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/2228240), [Who/Do/Be/Feel](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/884738), [Client Q/A](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/7831631) |
| Assessment design | [ESG ranking](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/2195459), [Criteria list development](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/5144613), [Social and Environmental scope](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/10453040) |
| Architecture | [Diagrams](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/3768381), [As-built](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/16351289), [AWS architecture](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/13041670), [Backend pipeline](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/7667797), [Frontend pipeline](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/7667789), [LLM API](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/3670043) |
| Engineering | [Coding standards and PR review](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/12615766), [Git and PR strategy](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/15958018), [Deployment plan](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/12615743), [Tools we use](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/16351316) |
| Testing | [Testing strategy and results](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/7667807), [Test run 25 Oct](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/16252939), [UAT](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/16286078), [Validation](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/16318600) |
| Process | [Decisions log](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/7733327), [Meeting notes](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/2261063), [Handover meeting minutes](https://provisionitesg.atlassian.net/wiki/spaces/PEP/pages/18415618) |

In the repository: [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md),
[DEPLOY.md](DEPLOY.md), [docs/deploy-aws.md](docs/deploy-aws.md),
[docs/database.md](docs/database.md), [docs/analytics.md](docs/analytics.md),
[DEMO.md](DEMO.md), [frontend/CONNECTING.md](frontend/CONNECTING.md).

If Provision IT does not keep the Atlassian site, export the space as PDF
(Space settings > Export space) before the team's access ends.

## 17. Changelog and licence

- Every change since the first release, by version and sprint:
  [CHANGELOG.md](CHANGELOG.md). Releases are tagged on GitHub (v1.2.0 Sprint 2,
  v1.3.0 handover).
- Ownership and licence: [LICENSE](LICENSE). The code belongs to Provision IT
  Pty Ltd.
- Open-source components and their licences:
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
