# AI Job Application Agent

> Autonomous AI system that discovers jobs, scores them against your resume, tailors the resume and cover letter using a local LLM, and tracks every application in PostgreSQL — end-to-end.

---

## What It Does

Most job-automation projects stop at resume generation or basic matching. This system runs the full pipeline:

- **Job ingestion** — mock, API, and RSS adapters with deduplication
- **AI match scoring** — two-tier scorer (v1 weighted + v2 structured) with skill, role, experience, tool, and keyword sub-scores
- **Decision controller** — multi-layer filter that converts scores into HIGH / MEDIUM / LOW / REJECT decisions
- **Resume tailoring** — local LLM (Ollama) rewrites and emphasises existing resume content for each JD
- **Cover letter generation** — LLM-generated, grounded in resume facts only
- **Application tracking** — full PostgreSQL schema with status, outcome history, and audit fields
- **Auto-apply pipeline** — delivers via email (SMTP) or HTTP endpoint, with retry logic and rate limiting
- **Streamlit UI** — browse applications, view scores, update statuses

---

## Pipeline Flow

```
Job Source (mock / API / RSS)
        ↓
  Job Filter (quality, spam, role)
        ↓
  Match Scorer v2 (skill · role · experience · tools · keywords)
        ↓
  Decision Controller (HIGH / MEDIUM / LOW / REJECT)
        ↓
  Resume Tailor  +  Cover Letter  (Ollama LLM)
        ↓
  Auto-Apply (email or endpoint)
        ↓
  PostgreSQL  ←→  FastAPI  ←→  Streamlit UI
```

---

## Architecture

```
[Streamlit UI]  [CLI runner]  [Scheduler]
        ↓               ↓           ↓
           [FastAPI — port 8000]
          /         |          \
   [PostgreSQL]  [Ollama LLM]  [Auto-Apply Engine]
```

**API routes** (all require `X-API-KEY` header):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/match` | Score a JD against the stored resume |
| `POST` | `/tailor` | Tailor the resume for a JD |
| `POST` | `/cover-letter` | Generate a cover letter |
| `POST` | `/applications/` | Save an application record |
| `GET`  | `/applications/` | List applications (paginated) |
| `GET`  | `/applications/{id}` | Get a single application |
| `PATCH`| `/applications/{id}` | Update application status |
| `GET`  | `/health` | Health check |

---

## Match Scoring

### Scorer v1 (resume JSON → JD)
Weighted sub-scores on a resume dict:

| Sub-score | Weight | Description |
|-----------|--------|-------------|
| Skill coverage | 0.40 | % of resume skills found in JD |
| JD demand | 0.20 | % of JD skill demand the resume covers |
| Experience | 0.30 | Seniority signal alignment |
| Role alignment | 0.10 | Keyword overlap on role/domain terms |

### Scorer v2 (free-text resume → JD)
Structured sub-scores parsed from plain text:

| Sub-score | Weight | Description |
|-----------|--------|-------------|
| Skill | 0.40 | Required skill coverage |
| Role | 0.20 | Role group match (exact / same-group / cross-group) |
| Experience | 0.20 | Directional level match (junior / mid / senior) |
| Tools | 0.10 | Tool/technology coverage |
| Keywords | 0.10 | Domain keyword overlap (capped at 0.5) |

**Decision thresholds (v2):** HIGH ≥ 0.70 · MEDIUM ≥ 0.45 · LOW ≥ 0.25 · REJECT < 0.25

### Decision Controller
Multi-layer filter applied after scoring:

1. REJECT / LOW tier → skip
2. Skill coverage below configurable threshold → skip
3. Role score = 0 (cross-group mismatch) → skip
4. Experience score = 0 (two+ levels below) → downgrade one tier
5. Remaining HIGH / MEDIUM → apply

---

## Quick Start

### 1. Install

```bash
./setup.sh
source .venv/bin/activate
```

Or manually:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set API_KEY, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
```

### 3. Start Ollama

```bash
ollama pull qwen2.5-coder
ollama serve
```

### 4. Run the API

```bash
make run
# or: uvicorn app.main:app --reload --port 8000
```

The API initialises the database schema automatically on startup.

### 5. Seed your resume

Insert a resume into the `resumes` table with `version_name = 'base_v2'` (or whatever `RESUME_VERSION` is set to):

```sql
INSERT INTO resumes (version_name, content)
VALUES ('base_v2', '{"name":"...","skills":[...],"summary":"...","experience":[...]}');
```

### 6. Run the pipeline smoke test

```bash
python -m app.test_pipeline
```

### 7. Run the automation runner

```bash
python automation/runner.py
# Results saved to run_results.json
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | No | `development` | `development` or `production` |
| `DEBUG` | No | auto | `true`/`false`; auto-true in dev |
| `PORT` | No | `8000` | FastAPI server port |
| `APP_NAME` | No | `ai-job-agent-api` | Service name in logs |
| `API_KEY` | **Yes** | — | Bearer token for all protected routes |
| `DB_HOST` | **Yes** | — | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_NAME` | **Yes** | — | PostgreSQL database name |
| `DB_USER` | **Yes** | — | PostgreSQL user |
| `DB_PASSWORD` | **Yes** | — | PostgreSQL password |
| `OLLAMA_BASE_URL` | No | `http://127.0.0.1:11434` | Ollama server URL |
| `MODEL_NAME` | No | `qwen2.5-coder` | Ollama model for LLM calls |
| `LLM_TIMEOUT` | No | `180` | LLM request timeout in seconds |
| `RESUME_VERSION` | No | `base_v2` | Resume version key in the `resumes` table |
| `LOG_LEVEL` | No | auto | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `CORS_ORIGINS` | Prod only | localhost | Comma-separated allowed origins |
| `RATE_LIMIT_MAX_REQUESTS` | No | `10` | Per-IP rate limit (requests) |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate limit window (seconds) |
| `BASE_URL` | No | `http://127.0.0.1:8000` | Backend URL for CLI runner and auto-apply |

For the Streamlit frontend, copy `.env.streamlit.example` to `.env.streamlit`:

| Variable | Description |
|----------|-------------|
| `BACKEND_URL` | FastAPI backend URL |
| `API_KEY` | Same API key as the backend |

---

## Database Schema

Tables are created automatically on startup via idempotent migrations:

| Table | Description |
|-------|-------------|
| `resumes` | Resume JSON by version name |
| `applications` | Full application records (job, scores, resume, cover letter, status, outcome) |
| `application_logs` | Event log per application |
| `schema_migrations` | Applied migration versions |

Schema migrations run in order (v1 → v4) and are safe to re-run — every statement is idempotent.

---

## Auto-Apply Pipeline (`auto_apply/`)

Standalone pipeline that processes a job list end-to-end:

1. Scores each job via `/match`
2. Skips REJECT and LOW decisions
3. Calls `/tailor` and `/cover-letter` for HIGH and MEDIUM jobs
4. Delivers via email (`apply_email`) or HTTP endpoint (`apply_endpoint`)
5. Retries once on sender failure
6. Saves the application record via `POST /applications/`
7. Logs all outcomes to `auto_apply/job_logs.jsonl`
8. Enforces per-run job cap and inter-job delays

Additional env vars for email delivery:

| Variable | Description |
|----------|-------------|
| `EMAIL_HOST` | SMTP host |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USER` | SMTP username |
| `EMAIL_PASS` | SMTP password |

---

## Automation Runner (`automation/runner.py`)

Higher-level runner with a built-in job list. Processes jobs sequentially, prints a decision/status summary, and saves results to `run_results.json`:

```bash
python automation/runner.py

# Or pass a single JD from the CLI:
python automation/runner.py "Looking for a Python data analyst..."
```

---

## Job Filtering (`automation/job_filter.py`)

Filters raw job records before they enter the pipeline. Rules applied in order:

1. Description shorter than 50 characters → remove
2. All-caps title (only uppercase letters and spaces) → remove
3. More than 5 consecutive punctuation chars, or punctuation ratio > 20% → remove
4. Title or description matches a spam keyword → remove
5. `JOB_FILTER_ALLOWED_TITLES` set → keep only matching titles
6. `JOB_FILTER_BLOCKED_TITLES` set → remove matching titles

Configure via environment variables:

| Variable | Description |
|----------|-------------|
| `JOB_FILTER_SPAM_KEYWORDS` | Comma-separated spam keywords |
| `JOB_FILTER_ALLOWED_TITLES` | Comma-separated allowed title keywords |
| `JOB_FILTER_BLOCKED_TITLES` | Comma-separated blocked title keywords |

---

## Testing

```bash
# All tests
python -m pytest tests/ -v

# Specific suites
python -m pytest tests/test_scorer_v2_examples.py -v
python -m pytest tests/test_scorer_v2_properties.py -v
python -m pytest tests/test_decision_controller_properties.py -v
python -m pytest tests/test_preservation.py -v
python -m pytest tests/automation/ -v
```

Tests use [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing. The suite covers 165 tests across:

- Scorer v1 and v2 correctness properties
- Decision controller multi-layer logic
- LLM error handling (RuntimeError on failure paths)
- Input validation preservation
- Job filter quality, spam, and role rules
- Job ingestion deduplication and fingerprinting

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL (psycopg2, raw SQL) |
| LLM | Ollama (local, `qwen2.5-coder` default) |
| UI | Streamlit |
| Testing | pytest + Hypothesis |
| Config | python-dotenv |
| Production server | Gunicorn + Uvicorn workers |

---

## Limitations

- Requires a locally running Ollama instance — can be swapped for OpenAI or any other provider by replacing `ollama_client.py`
- Email delivery requires a configured SMTP server
- Job ingestion currently uses mock data by default; real API/RSS adapters are stubs ready to be implemented
- LLM calls can take 60–180 seconds depending on model size and hardware
