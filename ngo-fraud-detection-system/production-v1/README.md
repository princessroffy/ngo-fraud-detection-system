# NGO Fraud & Beneficiary Integrity System - Production V1

This folder contains a production-oriented upgrade path for the Streamlit prototype. It uses a React frontend, FastAPI backend, PostgreSQL database, Supabase authentication, role-based access control, audit logs, reviewer decisions, configurable fraud weights, upload history, privacy masking, and PDF reporting.

## Architecture

```text
React frontend
|
Supabase Auth
|
FastAPI backend
|
PostgreSQL
```

## Production Features

- Reviewer workflow with `Pending Review`, `Approved`, `Rejected`, `Needs Investigation`, and `Resolved` statuses.
- PostgreSQL storage for uploads, scored records, review status, reviewer notes, and audit logs.
- Supabase JWT authentication with `Admin`, `Reviewer`, and `Viewer` roles.
- Audit log for upload, review, and settings changes.
- Reviewer notes on each record.
- Batch upload history with file name, upload date, total records, high-risk count, review rate, and uploader.
- Admin-configurable fraud scoring weights.
- PDF fraud summary report export.
- Role-aware masking for phone numbers and email addresses.
- Render, Railway, and AWS deployment notes.

## Folder Layout

```text
production-v1/
|
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- models.py
|   |   |-- schemas.py
|   |   |-- security.py
|   |   |-- routers/
|   |   `-- services/
|   `-- requirements.txt
|
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- index.html
|
|-- docker-compose.yml
|-- .env.example
`-- README.md
```

## Local Development

Start PostgreSQL:

```bash
cd production-v1
docker compose up -d postgres
```

Backend:

```bash
cd production-v1/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

For local development without Supabase configured, add `AUTH_MODE=dev` to your local backend `.env`. Do not commit that file.

Frontend:

```bash
cd production-v1/frontend
cp .env.example .env
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Supabase Role Setup

Create users in Supabase Auth and add a role to user metadata:

```json
{
  "role": "Admin"
}
```

Supported roles:

- `Admin`: upload data, review records, change scoring weights, export reports, read audit logs.
- `Reviewer`: upload data, review records, export reports.
- `Viewer`: view masked records and dashboards only.

The backend validates Supabase JWTs using `JWT_SECRET`.

## API Summary

| Method | Endpoint | Role | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Health check |
| `GET` | `/api/me` | Any authenticated role | Current user profile |
| `POST` | `/api/uploads` | Admin, Reviewer | Upload CSV and score records |
| `GET` | `/api/uploads` | Any authenticated role | Batch upload history |
| `GET` | `/api/records` | Any authenticated role | Search and filter records |
| `PATCH` | `/api/records/{record_id}/review` | Admin, Reviewer | Save review decision and notes |
| `GET` | `/api/settings/fraud-weights` | Admin | List scoring weights |
| `PATCH` | `/api/settings/fraud-weights/{rule_key}` | Admin | Update a scoring weight |
| `GET` | `/api/audit` | Admin | Read audit trail |
| `GET` | `/api/reports/batches/{batch_id}.pdf` | Admin, Reviewer | Export PDF report |

## Deployment Notes

Render:

- Deploy PostgreSQL as a managed database.
- Deploy `backend/` as a Python web service.
- Deploy `frontend/` as a static site.
- Set environment variables from `.env.example`.

Railway:

- Add PostgreSQL plugin.
- Deploy backend and frontend as separate services.
- Use Railway variables for database and Supabase secrets.

AWS:

- Use RDS PostgreSQL.
- Deploy backend on ECS, App Runner, or Elastic Beanstalk.
- Deploy frontend on S3 plus CloudFront.
- Store secrets in AWS Secrets Manager or SSM Parameter Store.

## Privacy Notes

- Viewer role receives masked phone and email values.
- Admin and Reviewer roles can see raw contact data for verification.
- Audit logs track review and settings actions.
- Uploaded beneficiary data should only be stored in protected environments with proper consent and access controls.

## Important Limitation

Fraud scores are decision-support signals. They should never be used as automatic proof of fraud or as the only basis for denying aid.
