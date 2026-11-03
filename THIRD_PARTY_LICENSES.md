# Third-party licences

The platform is owned by Provision IT Pty Ltd (see [LICENSE](LICENSE)). It is
built on the open-source components below, which keep their own licences. All
of them allow commercial use. Versions are the ones tested at handover
(November 2026).

**Obligations in short:** keep the copyright notices that ship with each
component (they are already in the vendored files and installed packages). The
one copyleft component is psycopg (LGPL-3.0). It is used unmodified as an
installed library, which the LGPL allows in closed-source software. If you ever
change psycopg's own source, publish those changes.

## Backend (Python, `backend/requirements.txt`)

| Package | Version tested | Licence | Used for |
|---|---|---|---|
| FastAPI | 0.162.0 | MIT | Web API |
| Uvicorn | 0.54.0 | BSD-3-Clause | API server |
| HTTPX | 0.28.1 | BSD-3-Clause | Fetching company websites, Gemini API calls |
| Beautiful Soup 4 | 4.15.0 | MIT | Reading HTML pages |
| lxml | 6.1.3 | BSD-3-Clause | HTML parser |
| pdfplumber | 0.11.10 | MIT | Page-numbered PDF text |
| pypdf | 6.21.4 | BSD-3-Clause | PDF metadata and fallback reading |
| Pydantic | 2.14.2 | MIT | Request and response models |
| ReportLab | 5.1.0 | BSD-3-Clause | PDF reports |
| python-multipart | 0.0.33 | Apache-2.0 | File uploads |
| SQLAlchemy | 2.1.6 | MIT | Database access |
| PyJWT | 2.15.1 | MIT | Sign-in tokens |
| psycopg 3 | 3.3.7 | LGPL-3.0-only | PostgreSQL driver |

Base image: `python:3.12-slim` (Docker Official Image; Python itself is under
the PSF License).

## Frontend (vendored in `frontend/vendor/`, no build step)

| Component | Version | Licence | Notes |
|---|---|---|---|
| React, React DOM | 18.3.1 | MIT | Notice kept in the file header |
| Babel Standalone | 7.x | MIT | Compiles the page's JSX in the browser |
| posthog-js | 1.435.5 | MIT | Notice in `frontend/vendor/posthog-LICENSE`. Off until a key is set |
| Archivo | 600, 700, 800 | SIL Open Font License 1.1 | Headings |
| Inter | 400, 500, 600 | SIL Open Font License 1.1 | Body text |
| IBM Plex Mono | 400, 500 | SIL Open Font License 1.1 | Labels, codes, figures |

The PDF report embeds the same three families from `backend/app/fonts/` (TTF, same licence).

The OFL lets you use, embed and self-host the fonts commercially. It only
forbids selling the font files on their own.

## Deployment and testing tools (not shipped to users)

| Tool | Licence | Used for |
|---|---|---|
| Wrangler | MIT OR Apache-2.0 | Cloudflare deploys |
| @cloudflare/containers | See its package | Running the API image on Cloudflare |
| Playwright | Apache-2.0 | Browser tests |
| esbuild | MIT | Checks the Worker bundles in CI |
| Ruff | MIT | Python lint |
| GitHub Actions (`actions/*`) | MIT | CI and CD |

## External services (accounts, not code)

These are services the platform calls. Each needs Provision IT's own account
and is governed by that provider's terms, not by a code licence. Setup is in
[HANDOVER.md](HANDOVER.md#6-accounts-api-keys-and-credentials).

| Service | Needed? | Terms to check |
|---|---|---|
| Google Gemini API | Optional (keyword matching works without it) | Free tier prompts may be used by Google to improve its models. Use a paid tier for confidential work |
| Cloudflare Workers Paid | For the current hosting | US$5 a month |
| Neon PostgreSQL | For the current hosting | Free tier is enough at current volume |
| Amazon Web Services | If hosting moves to AWS | See [docs/deploy-aws.md](docs/deploy-aws.md) |
| PostHog | Optional | Session replay masks inputs and email addresses |
| SMTP provider (Gmail, SES) | Optional | Outreach to companies must follow the Spam Act 2003 |
