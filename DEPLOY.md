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

## Every update after that

```
cd cloudflare
npx wrangler deploy
```

Secrets and the database carry over.

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
