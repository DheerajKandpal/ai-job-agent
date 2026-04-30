# AI Job Application Agent

End-to-end AI system that automates job applications — from job description → match scoring → tailored resume → cover letter → tracked in PostgreSQL.

---

## What It Does

Give it a job description and it will:

- Score your fit (match score + matched/missing skills)
- Generate a tailored resume via LLM
- Generate a personalized cover letter via LLM
- Store the full application in PostgreSQL
- Run automatically on a schedule (cron / automation runner)
- Auto-apply to jobs via email or HTTP endpoint (auto-apply pipeline)

---

## Architecture

```
[Streamlit UI / CLI / Cron]
         |
         v
   [FastAPI Backend]
         |
    +----+----+
    |         |
    v         v
[PostgreSQL] [Ollama LLM]
```

**Modules:**

| Module | Purpose |
|---|---|
| `app/` | FastAPI backend — routes, services, middleware, config |
| `app/services/matcher/` | Skill-based resume-to-job match scoring |
| `app/services/tracker/` | PostgreSQL persistence (resumes, applications) |
| `app/services/llm/` | Ollama LLM client for resume tailoring and cover letters |
| `auto_apply/` | Autonomous job application pipeline (score → tailor → send) |
| `automation/` | Cron scheduler and automation runner |
| `streamlit_app.py` | Streamlit UI frontend |
| `run_pipeline.py` | CLI pipeline runner (no UI required) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/match` | Score resume against job description |
| `POST` | `/tailor` | Generate tailored resume |
| `POST` | `/cover-letter` | Generate cover letter |
| `GET` | `/applications/` | List applications (paginated) |
| `POST` | `/applications/` | Save a new application |
| `GET` | `/applications/{id}` | Get application by ID |
| `PATCH` | `/applications/{id}` | Update application status |

All routes (except `/` and `/health`) require `Authorization: Bearer <API_KEY>`.

---

## Quick Start

```bash
# 1. Create venv, install deps, copy .env.example → .env
make setup

# 2. Edit .env with real values (DB, API key, Ollama URL)
nano .env

# 3. Start FastAPI + Streamlit
make run
```

- API → http://127.0.0.1:8000
- UI  → http://127.0.0.1:8501

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `development` | `development` or `production` |
| `DEBUG` | No | auto | `true`/`false`; defaults to `true` in dev |
| `PORT` | No | `8000` | FastAPI server port |
| `APP_NAME` | No | `ai-job-agent-api` | Service name in logs |
| `API_KEY` | **Yes** | — | Bearer token for protected routes |
| `DB_HOST` | **Yes** | — | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_NAME` | **Yes** | — | PostgreSQL database name |
| `DB_USER` | **Yes** | — | PostgreSQL user |
| `DB_PASSWORD` | **Yes** | — | PostgreSQL password |
| `OLLAMA_BASE_URL` | No | `http://127.0.0.1:11434` | Ollama server URL |
| `MODEL_NAME` | No | `qwen2.5-coder` | Ollama model for LLM calls |
| `LOG_LEVEL` | No | auto | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `CORS_ORIGINS` | Prod only | localhost | Comma-separated allowed origins |
| `RESUME_VERSION` | No | `base_v2` | Resume version key in DB |
| `LLM_TIMEOUT` | No | `30` | LLM request timeout (seconds) |
| `RATE_LIMIT_MAX_REQUESTS` | No | `10` | Per-IP rate limit (requests) |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate limit window (seconds) |

For the Streamlit frontend, copy `.env.streamlit.example` to `.env.streamlit`:

| Variable | Description |
|---|---|
| `BACKEND_URL` | FastAPI backend URL |
| `API_KEY` | Same API key as the backend |

---

## Auto-Apply Pipeline

The `auto_apply/` module runs an autonomous application pipeline:

1. Scores each job (keyword match, title relevance, apply method, description length, company presence)
2. Skips low/medium-tier jobs (threshold: 80+ for high tier)
3. Calls `/tailor` and `/cover-letter` for high-tier jobs
4. Delivers via email (`apply_email`) or HTTP endpoint (`apply_endpoint`)
5. Retries once on sender failure
6. Updates application status via `PATCH /applications/{id}`
7. Logs all outcomes to `auto_apply/job_logs.jsonl`
8. Enforces a per-run cap of 20 jobs with 30–60s inter-job delays

Additional env vars for auto-apply:

| Variable | Description |
|---|---|
| `BASE_URL` | Backend URL (default: `http://127.0.0.1:8000`) |
| `EMAIL_HOST` | SMTP host (required for email delivery) |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USER` | SMTP username |
| `EMAIL_PASS` | SMTP password |

---

## CLI Pipeline

Run the full pipeline without the UI:

```bash
python run_pipeline.py --job-description "..." --job-title "Engineer" --company "Acme"

# Or from a file:
python run_pipeline.py --job-description-file job.txt --job-title "Engineer" --company "Acme"
```

Requires `BACKEND_URL` and `API_KEY` in `.env`.

---

## Database Schema

Three tables are auto-created on startup:

- `resumes` — stores resume JSON by version name
- `applications` — stores full application records (job, match score, resume, cover letter, status)
- `application_logs` — event log per application
- `schema_migrations` — tracks applied schema versions

---

## Testing

```bash
# Syntax/compile check
make test

# Property-based tests (auto_apply pipeline)
python -m pytest auto_apply/tests/ -v

# All tests
python -m pytest -v
```

Property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/) to verify 13 correctness properties of the auto-apply pipeline.

---

## Tech Stack

- **FastAPI** — backend API
- **PostgreSQL** — application storage
- **Streamlit** — UI frontend
- **Ollama** — local LLM (resume tailoring, cover letters)
- **Gunicorn + Uvicorn** — production WSGI/ASGI server
- **Hypothesis** — property-based testing
- **python-dotenv** — environment config

---

## Limitations

- Uses a local Ollama LLM — can be extended to OpenAI or other providers
- Auto-apply email delivery requires a configured SMTP server
- No built-in job scraper — jobs must be provided programmatically
