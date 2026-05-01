# 🚀 AI Job Application Agent

> Autonomous AI system that **discovers jobs, tailors resumes, generates cover letters, and applies automatically — end-to-end.**

---

## 🔥 What Makes This Different

Most projects stop at:

* resume generation ❌
* job matching ❌

This system does:

✔ Job discovery (API + scraping)
✔ AI-based filtering (match scoring)
✔ Resume tailoring (LLM)
✔ Cover letter generation
✔ **Auto-apply (email + endpoint)**
✔ Application tracking (PostgreSQL)

👉 **End-to-end automation, not just components**

---

## ⚡ 30-Second Demo Flow

```text
Internet Jobs
     ↓
Filter (AI Match Score)
     ↓
Tailored Resume + Cover Letter
     ↓
Auto Apply (Email / Endpoint)
     ↓
Track Applications
```

---

## 🎯 Why This Matters

Applying manually is:

* repetitive
* inconsistent
* time-consuming

This system converts it into:

> **a scalable, automated pipeline with AI decision-making**

---

## 🧠 Key Engineering Decisions

* **No ORM** → direct SQL for control & performance
* **Local LLM (Ollama)** → privacy + zero API cost
* **Hybrid job sourcing** → power + safety balance
* **Controlled automation** → avoids platform bans

---

## 🏗️ Architecture (Simplified)

```text
[Streamlit UI / CLI / Scheduler]
            ↓
       [FastAPI]
      /         \
[PostgreSQL]   [LLM]
      ↓
 [Auto Apply Engine]
```

---

## 📸 Screenshots (Add later)

* [ ] Job processing UI
* [ ] Generated resume
* [ ] Dashboard
* [ ] Application list

---

## 🚀 Quick Start

```bash
make setup
make run
```

* API → http://127.0.0.1:8000
* UI  → http://127.0.0.1:8501

---

## ⚠️ Reality Note

This system is designed for:

* **high-volume intelligent applications**

Not:

* blind mass spam

---


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
