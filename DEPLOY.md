# Deploying to Cloudflare

One Cloudflare Worker serves everything from one address
(`https://provisionit-esg.<your-subdomain>.workers.dev`):

```
browser ──> Worker (cloudflare/src/index.js)
              ├─ /api/*, /respond/*  ──> API container (backend/Dockerfile)
              │                              └─> PostgreSQL (Neon or any host)
              └─ everything else     ──> website files (frontend/)
```

- **Website:** `frontend/`, served as static files. It calls the API on its own
  domain, so there is no CORS setup and no API address to configure.
- **API:** the FastAPI backend, built from `backend/Dockerfile` and run as a
  [Cloudflare Container](https://developers.cloudflare.com/containers/). The
  offline demo company (TST) runs inside the same container, so the fixture demo
  works in the cloud too.
- **Database:** PostgreSQL. Container disks are wiped whenever the container
  sleeps, so nothing that must last is kept on disk. Accounts, runs, requests
  **and the files companies upload** are all stored in the database.

## What you need

| Thing | Why |
|---|---|
| Cloudflare account on the **Workers Paid** plan (US$5/month) | Containers are not on the free plan |
| **Docker Desktop**, running | Wrangler builds the API image on your machine |
| **Node.js 20+** | For Wrangler, Cloudflare's CLI |
| A **PostgreSQL** database | [Neon](https://neon.tech) free tier is enough. Supabase or RDS work too |

## First deploy

### 1. Make the database

Create a Neon project (any region, Sydney is closest). Copy the connection
string. It looks like:

```
postgresql://user:password@ep-something.ap-southeast-2.aws.neon.tech/neondb?sslmode=require
```

The API creates its tables on first start. Nothing to run.

### 2. Lock down sign-ups

The site will be on the public internet. Open `cloudflare/wrangler.jsonc` and
set who may create an account:

```jsonc
"SIGNUP_DOMAINS": "student.unimelb.edu.au,provisionit.com.au",
```

Left empty, **anyone** who finds the URL can sign up.

### 3. Install and log in

```
cd cloudflare
npm install
npx wrangler login
```

### 4. Deploy

```
npx wrangler deploy
```

This builds the API image with Docker, pushes it to Cloudflare and publishes the
Worker. It prints the site URL. **The first deploy takes a few minutes before the
container answers.** Until then, `/api/...` calls fail or hang.

### 5. Add the secrets

Each command asks for the value. Nothing goes in a file.

```
npx wrangler secret put DATABASE_URL      # the Neon connection string
npx wrangler secret put JWT_SECRET        # paste the output of: openssl rand -base64 48
npx wrangler secret put GEMINI_API_KEY    # optional: without it, keyword matching is used
```

Email (optional, same as `backend/.env`):

```
npx wrangler secret put SMTP_HOST         # smtp.gmail.com
npx wrangler secret put SMTP_PORT         # 587
npx wrangler secret put SMTP_USER         # the Gmail address
npx wrangler secret put SMTP_PASSWORD     # a Gmail app password, not the account password
npx wrangler secret put SMTP_FROM         # "Provision IT ESG <the Gmail address>"
```

Then deploy again, so the container starts with the secrets:

```
npx wrangler deploy
```

### 6. Check it

Open `https://<your site>/api/health`. You want:

- `"status": "ok"`
- `"authRequired": true`
- `"llmConfigured": true` if you set a Gemini key
- `"smtpConfigured": true` if you set SMTP

Then open the site, create an account and run **TST**.

## Every update after that: continuous deployment

Merging to `main` deploys on its own (`.github/workflows/deploy.yml`):

```
pull request ──> CI (lint, unit, acceptance, e2e, secret scan, image build)
                   │ reviewed and merged into integration
release PR ──> main ──> CI passes ──> approval on "production" ──> wrangler deploy ──> smoke test
```

1. CI must pass on `main`. A red CI never deploys.
2. The deploy job waits on the GitHub environment **production**; Agam (or the
   named backup) approves it in the Actions tab.
3. `npx wrangler deploy` publishes the Worker, website and API container. The
   commit hash is stored as the version message.
4. `scripts/smoke_test.sh` waits for the container to wake, then checks the
   site, the API, that sign-in is enforced and the matrix versions.

One-time setup in GitHub (Settings):

- **Secrets and variables > Actions:** `CLOUDFLARE_API_TOKEN` (a token with
  "Edit Cloudflare Workers") and `CLOUDFLARE_ACCOUNT_ID`.
- **Environments:** create `production`, add Agam as required reviewer.

App secrets (`DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`, `SMTP_*`) stay in
Cloudflare and are never copied into GitHub. Secrets and the database carry
over between deploys.

By hand, for example from a laptop:

```
cd cloudflare
npx wrangler deploy
bash ../scripts/smoke_test.sh https://provisionit-esg.provisionit-esg.workers.dev
```

## Rolling back

```
cd cloudflare
npx wrangler deployments list     # recent versions with their commit message
npx wrangler rollback             # back to the previous version
```

The database is not rolled back. Every schema change so far only adds tables or
columns, so an older version still runs against a newer database.

## Release responsibilities

| Step | Who | Backup |
|---|---|---|
| Review and merge feature PRs into `integration` | Named reviewer, then Agam merges | Pulitha |
| Release PR `integration` → `main` | Agam opens, Pulitha approves | Jun approves |
| Approve the production deploy | Agam | Pulitha |
| Watch the smoke test, roll back if it fails | Agam | Pulitha |
| Cloudflare and Neon secrets | Agam | none: shared through Cloudflare only |
| Tell the client what changed | Agam, from CHANGELOG.md | Jun |

## Good to know

- **Cold start.** The container sleeps after 30 idle minutes (`sleepAfter` in
  `cloudflare/src/index.js`). The next request wakes it in a few seconds. Before
  a client demo, open the site a minute early.
- **One instance.** Assessment progress is held in memory, so `max_instances` is
  1. Fine for a team and a client. Moving progress into the database would lift
  this.
- **Email might not leave Cloudflare.** If `smtpConfigured` is true but emails
  say "saved, not sent", the SMTP port is blocked from the container. Nothing
  breaks: every email is still recorded. The fix is an HTTP email API (Amazon
  SES, Resend or Cloudflare Email Service) in `backend/app/mailer.py`.
- **Links in request emails** use the site's own address automatically. Set
  `PUBLIC_BASE_URL` in `wrangler.jsonc` only if you add a custom domain and want
  emails to use it.
- **Health:** `/api/health` reports `llmConfigured` and `smtpConfigured`. If
  `llmConfigured` is false the live site reads documents by keyword matching,
  and every assessment says so.
- **Logs:** `npx wrangler tail` for the Worker. Container output is in the
  Cloudflare dashboard under Workers & Pages > provisionit-esg > Containers.
- **Never** put keys in `wrangler.jsonc` or commit `backend/.env`. Secrets go
  through `wrangler secret put` only.
- **Real companies:** do not send requests to real company addresses until Chris
  has checked them against the Spam Act. Use your own email as the contact.

## Running locally (unchanged)

```
./demo.sh            # fixture demo, SQLite, nothing leaves the laptop
./demo.sh --live     # also loads backend/.env (Gemini, SMTP)
```

To run the API container on your own machine:

```
docker build -t provisionit-esg-api backend
docker run -p 8080:8080 --env-file backend/.env provisionit-esg-api
```

## Files

| File | What it does |
|---|---|
| `cloudflare/wrangler.jsonc` | Worker, container and static-site settings |
| `cloudflare/src/index.js` | Routes `/api` and `/respond` to the container, the rest to `frontend/` |
| `backend/Dockerfile` | The API image |
| `backend/start.sh` | Container entrypoint: fixture company plus the API |
| `frontend/.assetsignore` | Keeps the Markdown notes off the public site |
