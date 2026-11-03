# Deploying to AWS

How to run the platform on Provision IT's own AWS account. The same Docker
image that runs on Cloudflare today runs on AWS unchanged; only hosting and
configuration change.

There are two stages:

- **Stage 1, lift and shift (this guide).** Works with the code as handed over.
  About half a day for someone comfortable in the AWS console.
- **Stage 2, the target design.** A queue and worker, S3 for files, Cognito
  sign-in, SES, Textract and Bedrock. Needs code changes; see
  [Stage 2](#stage-2-the-target-design) and the Confluence page *AWS deployment
  architecture*.

## Stage 1 architecture

```
                       https://esg.provisionit.com.au (or the CloudFront domain)
                                         |
                                    CloudFront
                     +-------------------+--------------------+
          default (*)|                                        | /api/*  /respond/*
                     v                                        v
           S3 bucket (private)                 Application Load Balancer (HTTP 80,
           frontend/ static files              only CloudFront may connect)
           read through Origin Access Control             |
                                                          v
                                               ECS Fargate service, 1 task
                                               image from ECR (backend/Dockerfile)
                                               port 8080, logs to CloudWatch
                                                          |
                              +---------------------------+------------------------+
                              v                           v                        v
                   RDS PostgreSQL               Secrets Manager            Internet (crawl company
                   (private subnet)             DATABASE_URL, JWT_SECRET,  sites, Gemini API,
                                                GEMINI_API_KEY, SMTP_*     SES SMTP)
```

Why this shape:

- **One address for site and API.** The frontend calls the API on its own
  origin (`frontend/index.html` sets `PROVISION_API_BASE = location.origin`), so
  CloudFront routing `/api/*` and `/respond/*` to the load balancer is all that
  is needed. No CORS, no API URL to configure. This mirrors the Cloudflare
  Worker exactly.
- **One task.** Assessment progress is held in memory, so the service must run
  exactly one task (see [Limits](#limits-and-how-to-lift-them)).
- **Nothing that must last is on disk.** Accounts, runs, requests and uploaded
  files are all in PostgreSQL, so a task can be replaced at any time.
- **Email through SES without code changes.** SES has an SMTP interface, and the
  platform already speaks SMTP.

## Before you start

| You need | Notes |
|---|---|
| An AWS account with admin access | Use region `ap-southeast-2` (Sydney) throughout |
| AWS CLI v2, logged in (`aws configure` or `aws sso login`) | For the push and deploy commands |
| Docker Desktop, running | To build the image |
| The repository, cloned | `git clone` of the transferred repo |
| A Gemini API key (optional) | https://aistudio.google.com/apikey. Without it the platform uses keyword matching and says so |
| A domain in Route 53 or elsewhere (optional) | Without one, use the `*.cloudfront.net` address |

Set these once in your terminal; the commands below use them:

```bash
export AWS_REGION=ap-southeast-2
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export APP=provisionit-esg
```

## Step 1. Network

Use the default VPC to start, or create a VPC with two public and two private
subnets across two availability zones (VPC console > Create VPC > *VPC and
more*, NAT gateways: **None**).

Create three security groups:

| Name | Inbound | Purpose |
|---|---|---|
| `esg-alb` | TCP 80 from the managed prefix list `com.amazonaws.global.cloudfront.origin-facing` | Only CloudFront can reach the load balancer |
| `esg-api` | TCP 8080 from `esg-alb` | Only the load balancer can reach the API |
| `esg-db` | TCP 5432 from `esg-api` | Only the API can reach the database |

The API task runs in a **public subnet with a public IP** so it can reach
company websites and the Gemini API without a NAT gateway (saves about US$35 a
month). Its security group still accepts traffic only from the load balancer.

## Step 2. Database (RDS PostgreSQL)

RDS console > Create database:

- Engine: PostgreSQL 16, template *Free tier* or *Dev/Test*
- Instance: `db.t4g.micro`, 20 GB gp3, storage autoscaling on
- DB name `esg`, master user `esg_admin`, password: let RDS manage it in
  Secrets Manager, or generate one and keep it safe
- Connectivity: your VPC, **private** subnets, public access **No**, security
  group `esg-db`
- Backups: 7 days. Deletion protection: on

The API creates its tables on first start. There is nothing to run. Your
connection string is:

```
postgresql://esg_admin:<password>@<rds-endpoint>:5432/esg?sslmode=require
```

## Step 3. Secrets

Secrets Manager > Store a new secret > *Other type of secret* > Plaintext. One
secret per value, named as below. Only the values you use are needed.

| Secret name | Value |
|---|---|
| `esg/DATABASE_URL` | The connection string from step 2 |
| `esg/JWT_SECRET` | Output of `openssl rand -base64 48` |
| `esg/GEMINI_API_KEY` | Your Gemini key (optional) |
| `esg/SMTP_PASSWORD` | SES SMTP password from step 7 (optional) |

Never put these in the repository, a task definition's plain environment, or a
GitHub variable. CI fails if a key is committed (`scripts/check_secrets.sh`).

## Step 4. Container registry (ECR) and the image

```bash
aws ecr create-repository --repository-name $APP-api --region $AWS_REGION
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker build --platform linux/amd64 -t $APP-api backend
docker tag $APP-api:latest $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$APP-api:latest
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$APP-api:latest
```

Build for `linux/amd64` even on an Apple Silicon Mac: Fargate below runs x86.

## Step 5. Load balancer

EC2 console > Target groups > Create:

- Type **IP addresses**, protocol HTTP, port **8080**, your VPC
- Health check path **`/api/health`**, success code 200
- Do not register targets; ECS does that

EC2 console > Load balancers > Create *Application Load Balancer*:

- Internet-facing, the two **public** subnets, security group `esg-alb`
- Listener HTTP 80 > forward to the target group
- Attributes: idle timeout 120 seconds (PDF reports on large runs can take a
  while)

## Step 6. ECS Fargate service

ECS console > Clusters > Create cluster `esg` (Fargate only).

Task definitions > Create new (JSON tab). Replace the account id, region and
secret ARNs (each secret's ARN is on its Secrets Manager page):

```json
{
  "family": "provisionit-esg-api",
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "512",
  "memory": "1024",
  "runtimePlatform": { "cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX" },
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<ACCOUNT_ID>.dkr.ecr.ap-southeast-2.amazonaws.com/provisionit-esg-api:latest",
      "essential": true,
      "portMappings": [{ "containerPort": 8080, "protocol": "tcp" }],
      "environment": [
        { "name": "AUTH_REQUIRED", "value": "true" },
        { "name": "SIGNUP_DOMAINS", "value": "provisionit.com.au" },
        { "name": "GEMINI_MODEL", "value": "gemini-3.6-flash" },
        { "name": "JWT_EXPIRE_MINUTES", "value": "480" },
        { "name": "PUBLIC_BASE_URL", "value": "https://<your CloudFront domain>" },
        { "name": "SMTP_HOST", "value": "email-smtp.ap-southeast-2.amazonaws.com" },
        { "name": "SMTP_PORT", "value": "587" },
        { "name": "SMTP_USER", "value": "<SES SMTP user name>" },
        { "name": "SMTP_FROM", "value": "Provision IT ESG <esg@provisionit.com.au>" }
      ],
      "secrets": [
        { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:<ACCOUNT_ID>:secret:esg/DATABASE_URL-xxxxxx" },
        { "name": "JWT_SECRET", "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:<ACCOUNT_ID>:secret:esg/JWT_SECRET-xxxxxx" },
        { "name": "GEMINI_API_KEY", "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:<ACCOUNT_ID>:secret:esg/GEMINI_API_KEY-xxxxxx" },
        { "name": "SMTP_PASSWORD", "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:<ACCOUNT_ID>:secret:esg/SMTP_PASSWORD-xxxxxx" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/provisionit-esg-api",
          "awslogs-create-group": "true",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ]
}
```

Leave out the SMTP lines (and the `SMTP_PASSWORD` secret) to start: with no
`SMTP_HOST`, every email is recorded in the app instead of sent, which is the
safe default.

The execution role needs `secretsmanager:GetSecretValue` on the `esg/*`
secrets. In IAM, open `ecsTaskExecutionRole` (ECS creates it the first time)
and add an inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "secretsmanager:GetSecretValue",
    "Resource": "arn:aws:secretsmanager:ap-southeast-2:<ACCOUNT_ID>:secret:esg/*"
  }]
}
```

Cluster `esg` > Services > Create:

- Task definition `provisionit-esg-api`, desired tasks **1**
- Deployment: minimum healthy **0%**, maximum **100%**. This stops two tasks
  running at once during a deploy, which would split in-memory progress. A
  deploy therefore has about a minute of downtime.
- Networking: **public** subnets, security group `esg-api`, public IP **on**
- Load balancing: the ALB and target group from step 5, container `api:8080`

Wait until the target group shows the task as *healthy*.

## Step 7. Website (S3 and CloudFront)

Create a private bucket (Block all public access: on) and upload the frontend:

```bash
aws s3 mb s3://$APP-web-$ACCOUNT_ID --region $AWS_REGION
aws s3 sync frontend s3://$APP-web-$ACCOUNT_ID --delete \
  --exclude "*.md" --exclude ".assetsignore"
```

CloudFront > Create distribution:

1. **Origin 1:** the S3 bucket, *Origin access control* (create one), then
   paste the bucket policy CloudFront offers into the bucket.
2. **Default behaviour (`*`)** to origin 1: redirect HTTP to HTTPS, cache
   policy *CachingOptimized*. Default root object `index.html`.
3. **Origin 2:** the load balancer's DNS name, protocol **HTTP only**, port 80.
4. **Behaviours `/api/*` and `/respond/*`** to origin 2: allowed methods
   **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**, cache policy
   **CachingDisabled**, origin request policy **AllViewerExceptHostHeader**.
   Both are needed: `/respond/*` is the page companies open from a request
   email.
5. Optional: add your domain under *Alternate domain names* with an ACM
   certificate issued in **us-east-1**, then point the domain's DNS at the
   distribution.

Set `PUBLIC_BASE_URL` in the task definition to the final address (the
CloudFront domain or your own) and redeploy the service, so links in request
emails point to the right place.

## Step 8. Email through SES (optional)

1. SES console > Identities > verify the domain `provisionit.com.au` (add the
   DKIM records it gives you).
2. Request production access (new accounts can only send to verified
   addresses).
3. SMTP settings > Create SMTP credentials. Put the user name in `SMTP_USER`
   and the password in the `esg/SMTP_PASSWORD` secret, then redeploy.

Before emailing real companies, have outreach checked against the Spam Act
2003. Until then, use your own address as the company contact.

## Step 9. Check it

```bash
bash scripts/smoke_test.sh https://<your CloudFront domain>
```

The smoke test is read-only. It checks that the site and API answer, sign-in is
enforced, unknown request links return 404 and the three matrices are served.
Then open the site, create an account with an address on `SIGNUP_DOMAINS`, and
assess **TST**, the offline demo company that runs inside the container.

`/api/health` should show `"status": "ok"`, `"authRequired": true`,
`"llmConfigured": true` (if a Gemini key is set) and `"smtpConfigured": true`
(if SES is set).

## Updating

```bash
# API
docker build --platform linux/amd64 -t $APP-api backend
docker tag $APP-api:latest $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$APP-api:latest
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$APP-api:latest
aws ecs update-service --cluster esg --service provisionit-esg-api --force-new-deployment

# Website
aws s3 sync frontend s3://$APP-web-$ACCOUNT_ID --delete --exclude "*.md" --exclude ".assetsignore"
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*"
```

**Continuous deployment.** `.github/workflows/deploy-aws.yml` does the same
from GitHub Actions. It is started by hand from the Actions tab until you
connect it:

1. IAM > Identity providers > add `token.actions.githubusercontent.com`
   (OpenID Connect, audience `sts.amazonaws.com`).
2. Create a role `github-deploy-esg` that trusts that provider for your
   repository only, with permission to push to the ECR repository, update the
   ECS service, write to the web bucket and create CloudFront invalidations.
3. Repository Settings > Secrets and variables > Actions > **Variables**:
   `AWS_ROLE_ARN`, `AWS_REGION`, `ECR_REPOSITORY`, `ECS_CLUSTER`,
   `ECS_SERVICE`, `WEB_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `AWS_SITE_URL`.
   None of these are secret, and no AWS keys are stored in GitHub.
4. To deploy on every merge to `main`, add the `workflow_run` trigger from
   `deploy.yml` to `deploy-aws.yml`, and switch off `deploy.yml` if you are
   leaving Cloudflare.

## Rolling back

- **API:** ECS > service > Update > choose the previous task definition
  revision > Update. Or re-tag an earlier image as `latest` and force a new
  deployment.
- **Website:** `git checkout <previous tag> -- frontend`, sync and invalidate.
- **Database:** RDS > Automated backups > Restore to point in time (creates a
  new instance; point `esg/DATABASE_URL` at it). Schema changes so far only add
  tables and columns, so an older API runs against a newer database.

Take a manual RDS snapshot before every release.

## Moving the data from Cloudflare and Neon

Only needed if you want to keep accounts and past runs from the current site.

```bash
pg_dump "<Neon connection string>" --no-owner --no-acl -Fc -f esg.dump
pg_restore --no-owner --no-acl -d "<RDS connection string>" esg.dump
```

RDS is in a private subnet, so run `pg_restore` from a machine inside the VPC
(for example a temporary EC2 instance or CloudShell in the VPC), or restore
before switching public access off.

## Cost

Rough monthly cost in Sydney at the current volume (a few analysts, tens of
assessments a month). Check with the
[AWS Pricing Calculator](https://calculator.aws/) before committing.

| Item | About (US$ a month) |
|---|---|
| Fargate, 0.5 vCPU and 1 GB, always on | 18 |
| Application Load Balancer | 20 |
| RDS `db.t4g.micro`, 20 GB | 15 to 20 (free tier in a new account's first year) |
| Secrets Manager, 4 secrets | 2 |
| CloudFront, S3, CloudWatch logs, public IPv4 | 5 |
| **Total** | **about 60 to 65** |

Not included: Gemini API usage (pay per call; the free tier covers light use
but may use prompts for training) and SES (about US$0.10 per 1,000 emails).
The full Stage 2 design is estimated at about US$95 a month.

## Limits and how to lift them

| Limit | Why | Fix |
|---|---|---|
| One task, short downtime on deploy | Assessment progress is held in memory | Move progress into the `assessment_runs` table (Stage 2), then run 2 or more tasks behind the ALB |
| Long runs happen inside the API | No queue yet | SQS queue and a worker service (Stage 2) |
| Uploaded files live in the database | Container disks are temporary | Store them in S3 (Stage 2) |
| Scanned PDFs with no text layer are skipped | pdfplumber reads text only | Textract for scanned pages (Stage 2) |

## Stage 2: the target design

The Confluence page *AWS deployment architecture* is the full design. The code
work, in order:

1. **Progress in the database.** `pipeline.RunState` writes progress to
   `assessment_runs` instead of memory. This lifts the one-task limit.
2. **Queue and worker.** `POST /api/assessments` saves the run as QUEUED and
   sends a message to SQS; a second ECS service runs the same image with a
   worker command that takes jobs and calls `pipeline.run_assessment`.
3. **S3 for files.** Uploaded documents, harvested PDFs and reports go to S3,
   served through short-lived signed links.
4. **Cognito sign-in**, replacing the API's own JWT accounts, with MFA.
5. **Bedrock** as an alternative model provider in `backend/app/llm.py`, so
   prompts stay inside Provision IT's AWS account.
6. **EventBridge Scheduler** for the daily check that lapses overdue disclosure
   requests.
