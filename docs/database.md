# Database

Relational schema in `backend/app/db.py` (SQLAlchemy). SQLite at
`backend/data/platform.db` on a laptop; PostgreSQL on Amazon RDS in the
deployment design, selected with `DATABASE_URL`. Tables are created on first
start.

The issued result of an assessment is kept exactly as the API returned it
(`assessment_runs.payload`) so any report can be reproduced. Everything that
is listed, filtered, joined or audited also lives in its own columns and
tables.

```mermaid
erDiagram
    users ||--o{ assessment_runs : "requested_by"
    users ||--o{ disclosure_requests : "requested_by"
    users ||--o{ email_log : "sent_by"
    users ||--o{ revoked_tokens : "user_id"
    users ||--o{ companies : "created_by"
    companies ||--o{ assessment_runs : "company_id"
    companies ||--o{ disclosure_requests : "company_id"
    assessment_runs ||--o{ pillar_results : "run_id"
    assessment_runs ||--o{ source_documents : "run_id"
    assessment_runs ||--o{ disclosure_requests : "run_id"
    disclosure_requests ||--o{ request_items : "request_id"
    disclosure_requests ||--o{ request_documents : "request_id"

    users {
        string id PK
        string name
        string email UK
        string password_hash
        string role
        datetime created_at
        datetime last_login_at
    }
    revoked_tokens {
        string jti PK
        string user_id FK
        datetime expires_at
    }
    companies {
        int id PK
        string code UK
        string name
        string website
        string sector
        string tier
        bool listed
        string contact_email
        string created_by FK
    }
    assessment_runs {
        string id PK
        int company_id FK
        string requested_by FK
        string status
        string pillars
        string engine
        string model
        datetime requested_at
        datetime completed_at
        json payload
    }
    pillar_results {
        int id PK
        string run_id FK
        string pillar
        string matrix_version
        string band
        string confidence
        float transparency
        float practice
    }
    source_documents {
        int id PK
        string run_id FK
        string title
        string url
        string source_type
        string outcome
        string grade
        string provenance
    }
    disclosure_requests {
        string id PK
        string token UK
        int company_id FK
        string run_id FK
        string requested_by FK
        string contact_email
        string status
        bool delivered
        bool opt_out
        datetime created_at
        datetime due_at
        datetime responded_at
        datetime closed_at
        json detail
    }
    request_items {
        int id PK
        string request_id FK
        string criterion_code
        string pillar
        string status_at_request
    }
    request_documents {
        int id PK
        string request_id FK
        string title
        string path
        string media_type
        int bytes
        blob content "the file itself"
    }
    email_log {
        int id PK
        string kind
        string recipients
        string subject
        bool delivered
        string record_path
        string sent_by FK
        string run_id
        string request_id
        datetime created_at
    }
```

## Sign-in

`POST /api/auth/login` and `POST /api/auth/signup` return a JWT (HS256):

| Claim | Meaning |
|---|---|
| `sub` | user id |
| `name`, `email`, `role` | who is signed in |
| `iss` / `aud` | `provisionit-esg` / `provisionit-esg-api`, both checked |
| `iat`, `nbf`, `exp` | issued, valid from, expires (`JWT_EXPIRE_MINUTES`, default 480) |
| `jti` | unique id, recorded in `revoked_tokens` on sign-out |

Every `/api` route except health and sign-in requires
`Authorization: Bearer <token>`. Companies answering a disclosure request use
the single-purpose link token in their email and never sign in.

On AWS, Amazon Cognito issues the tokens and the API only verifies them;
`DATABASE_URL` points at RDS PostgreSQL (`pip install "psycopg[binary]"`).
