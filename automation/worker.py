"""
worker.py
---------
Parallel job processing worker for the AI job application pipeline.

Architecture
------------
- process_job(job, job_id)       — runs the full pipeline for a single job
- process_jobs_batch(jobs, ...)  — fans out jobs across a ThreadPoolExecutor

Each worker makes HTTP calls to the running FastAPI server, so parallelism
is at the I/O layer (HTTP + LLM wait time).  ThreadPoolExecutor is the right
primitive here: the work is I/O-bound, not CPU-bound.

Rate-limit awareness
--------------------
The server enforces 10 requests per 60 s per IP.  With max_workers=3 and
4 API calls per job (match, tailor, cover-letter, applications), a burst of
3 concurrent jobs = 12 calls.  A configurable stagger_seconds delay between
job submissions keeps the burst below the limit.

Result schema
-------------
Every job returns a JobResult dict:
    {
        "job_id":         int,
        "title":          str,
        "company":        str,
        "status":         "completed" | "rejected" | "logged" | "failed",
        "decision":       str | None,   # HIGH / MEDIUM / LOW / REJECT
        "score":          float | None,
        "application_id": int | None,
        "failed_at":      str | None,   # pipeline step where failure occurred
        "error":          str | None,   # exception message if status == "failed"
        "duration_s":     float,        # wall-clock seconds for this job
        "timestamp":      str,          # ISO-8601 UTC start time
    }
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
API_KEY  = os.getenv("API_KEY", "")

if not API_KEY:
    raise RuntimeError("Missing API_KEY — check .env loading")

_HEADERS = {
    "X-API-KEY":    API_KEY,
    "Content-Type": "application/json",
}

# Per-request HTTP timeout (seconds).  LLM endpoints can take up to
# 90 s × 3 retries + overhead; 310 s gives a safe margin.
_REQUEST_TIMEOUT = 310

# Valid decision values returned by /match
_VALID_DECISIONS = {"HIGH", "MEDIUM", "LOW", "REJECT"}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("automation.worker")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class JobResult(TypedDict):
    job_id:         int
    title:          str
    company:        str
    status:         str          # completed | rejected | logged | failed
    decision:       str | None
    score:          float | None
    application_id: int | None
    failed_at:      str | None
    error:          str | None
    duration_s:     float
    timestamp:      str


# ---------------------------------------------------------------------------
# Internal HTTP helper
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict, step: str, job_id: int) -> requests.Response | None:
    """
    POST *payload* to *url*.  Returns the Response or None on failure.
    Retries once on 5xx.  Logs all outcomes.
    """
    for attempt in (1, 2):
        try:
            resp = requests.post(
                url, headers=_HEADERS, json=payload, timeout=_REQUEST_TIMEOUT
            )
        except requests.Timeout:
            logger.warning("[JOB %s] %s timeout (attempt %s)", job_id, step, attempt)
            return None
        except Exception as exc:
            logger.error("[JOB %s] %s network error: %s", job_id, step, exc)
            return None

        if resp.status_code < 500:
            return resp

        logger.warning(
            "[JOB %s] %s server error %s (attempt %s)",
            job_id, step, resp.status_code, attempt,
        )
        if attempt == 2:
            return resp   # return the error response so caller can log body

    return None  # unreachable, satisfies type checker


def _parse_json(resp: requests.Response, step: str, job_id: int) -> dict | None:
    """Parse JSON from *resp*, returning None and logging on failure."""
    try:
        return resp.json()
    except Exception:
        logger.error(
            "[JOB %s] %s invalid JSON: %s", job_id, step, resp.text[:200]
        )
        return None


# ---------------------------------------------------------------------------
# Single-job worker
# ---------------------------------------------------------------------------

def process_job(job: dict, job_id: int) -> JobResult:
    """
    Run the full pipeline for one job.

    Pipeline stages
    ---------------
    1. match        — always runs
    2. tailor       — HIGH + MEDIUM only
    3. cover-letter — HIGH + MEDIUM only (MEDIUM: failure is non-fatal)
    4. applications — HIGH + MEDIUM only

    Returns a JobResult regardless of outcome.  Never raises.
    """
    t_start   = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()

    title   = job.get("title")   or "Unknown"
    company = job.get("company") or "Unknown"

    result: JobResult = {
        "job_id":         job_id,
        "title":          title,
        "company":        company,
        "status":         "failed",
        "decision":       None,
        "score":          None,
        "application_id": None,
        "failed_at":      None,
        "error":          None,
        "duration_s":     0.0,
        "timestamp":      timestamp,
    }

    def _finish(status: str, **kwargs) -> JobResult:
        result["status"]     = status
        result["duration_s"] = round(time.monotonic() - t_start, 2)
        result.update(kwargs)
        logger.info(
            "[JOB %s] %s/%s → %s (%.1fs)",
            job_id, title, company, status, result["duration_s"],
        )
        return result

    job_description = f"{title} at {company}\n\n{job.get('job_description', '')}"

    try:
        # ── STEP 1: MATCH ────────────────────────────────────────────────
        logger.info("[JOB %s] match start", job_id)
        resp = _post(f"{BASE_URL}/match", {"job_description": job_description}, "match", job_id)
        if resp is None or resp.status_code != 200:
            body = resp.text[:200] if resp is not None else "no response"
            logger.error("[JOB %s] match failed: %s", job_id, body)
            return _finish("failed", failed_at="match", error=f"match HTTP {getattr(resp, 'status_code', 'N/A')}")

        match_data = _parse_json(resp, "match", job_id)
        if match_data is None:
            return _finish("failed", failed_at="match", error="match invalid JSON")

        score    = float(match_data.get("match_score", 0.0))
        decision = match_data.get("decision", "REJECT")
        if decision not in _VALID_DECISIONS:
            decision = "REJECT"

        result["score"]    = score
        result["decision"] = decision
        logger.info("[JOB %s] match score=%.4f decision=%s", job_id, score, decision)

        # ── DECISION GATE ────────────────────────────────────────────────
        if decision == "LOW":
            logger.info("[JOB %s] LOW — logging only", job_id)
            return _finish("logged")

        if decision == "REJECT":
            logger.info("[JOB %s] REJECT — skipping", job_id)
            return _finish("rejected")

        # HIGH or MEDIUM — continue pipeline
        # ── STEP 2: TAILOR ───────────────────────────────────────────────
        logger.info("[JOB %s] tailor start", job_id)
        resp = _post(f"{BASE_URL}/tailor", {"job_description": job_description}, "tailor", job_id)
        if resp is None or resp.status_code != 200:
            body = resp.text[:200] if resp is not None else "no response"
            logger.error("[JOB %s] tailor failed: %s", job_id, body)
            return _finish("failed", failed_at="tailor", error=f"tailor HTTP {getattr(resp, 'status_code', 'N/A')}")

        tailor_data = _parse_json(resp, "tailor", job_id)
        if tailor_data is None:
            return _finish("failed", failed_at="tailor", error="tailor invalid JSON")
        logger.info("[JOB %s] tailor success", job_id)

        # ── STEP 3: COVER LETTER ─────────────────────────────────────────
        cover_letter_text: str | None = None
        logger.info("[JOB %s] cover-letter start", job_id)
        resp = _post(
            f"{BASE_URL}/cover-letter",
            {"job_description": job_description},
            "cover-letter",
            job_id,
        )
        if resp is None or resp.status_code != 200:
            body = resp.text[:200] if resp is not None else "no response"
            logger.warning("[JOB %s] cover-letter failed: %s", job_id, body)
            if decision == "HIGH":
                return _finish("failed", failed_at="cover-letter", error=f"cover-letter HTTP {getattr(resp, 'status_code', 'N/A')}")
            logger.info("[JOB %s] MEDIUM — continuing without cover letter", job_id)
        else:
            cl_data = _parse_json(resp, "cover-letter", job_id)
            if cl_data is not None:
                cover_letter_text = cl_data.get("cover_letter") or None
                logger.info("[JOB %s] cover-letter success", job_id)
            elif decision == "HIGH":
                return _finish("failed", failed_at="cover-letter", error="cover-letter invalid JSON")

        # ── STEP 4: STORE APPLICATION ────────────────────────────────────
        applications_payload = {
            "job_title":       title,
            "company":         company,
            "job_description": job_description,
            "match_score":     score,
            "resume_version":  "auto_v1",
            "cover_letter":    cover_letter_text,
        }
        logger.info("[JOB %s] applications start", job_id)
        resp = _post(f"{BASE_URL}/applications/", applications_payload, "applications", job_id)
        if resp is None or resp.status_code != 200:
            body = resp.text[:200] if resp is not None else "no response"
            logger.error("[JOB %s] applications failed: %s", job_id, body)
            return _finish("failed", failed_at="applications", error=f"applications HTTP {getattr(resp, 'status_code', 'N/A')}")

        app_data = _parse_json(resp, "applications", job_id)
        if app_data is None:
            return _finish("failed", failed_at="applications", error="applications invalid JSON")

        app_id = app_data.get("id")
        logger.info("[JOB %s] stored application_id=%s", job_id, app_id)
        return _finish("completed", application_id=app_id)

    except Exception as exc:
        # Final safety net — no job should crash the worker thread
        logger.exception("[JOB %s] unexpected error: %s", job_id, exc)
        return _finish("failed", error=f"unexpected: {exc}")


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

def process_jobs_batch(
    jobs: list[dict],
    max_workers: int = 3,
    stagger_seconds: float = 0.5,
) -> list[JobResult]:
    """
    Process *jobs* in parallel using a ThreadPoolExecutor.

    Parameters
    ----------
    jobs            : List of job dicts (same format as runner.py jobs list).
    max_workers     : Number of concurrent worker threads (default 3).
    stagger_seconds : Delay between job submissions to avoid rate-limit bursts.

    Returns
    -------
    list[JobResult]  Results in the same order as the input jobs list.
    """
    if not jobs:
        return []

    n = len(jobs)
    logger.info(
        "batch start: %d jobs, max_workers=%d, stagger=%.1fs",
        n, max_workers, stagger_seconds,
    )
    t_batch_start = time.monotonic()

    # Pre-allocate results list so we can fill by index (preserves input order)
    results: list[JobResult | None] = [None] * n

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-worker") as pool:
        # Submit jobs with a small stagger to spread the initial burst
        future_to_index: dict = {}
        for idx, job in enumerate(jobs):
            job_id = idx + 1
            future = pool.submit(process_job, job, job_id)
            future_to_index[future] = idx
            if idx < n - 1 and stagger_seconds > 0:
                time.sleep(stagger_seconds)

        # Collect results as they complete (order of completion, not submission)
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                # Should never happen since process_job catches everything,
                # but guard anyway.
                job = jobs[idx]
                logger.error("worker thread raised unexpectedly for job %d: %s", idx + 1, exc)
                results[idx] = JobResult(
                    job_id=idx + 1,
                    title=job.get("title") or "Unknown",
                    company=job.get("company") or "Unknown",
                    status="failed",
                    decision=None,
                    score=None,
                    application_id=None,
                    failed_at=None,
                    error=f"thread error: {exc}",
                    duration_s=0.0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

    total_s = round(time.monotonic() - t_batch_start, 2)

    # Cast away None (all slots filled above)
    final: list[JobResult] = [r for r in results if r is not None]

    # Summary
    status_counts   = Counter(r["status"]           for r in final)
    decision_counts = Counter((r["decision"] or "unknown") for r in final)

    logger.info("batch complete: %d jobs in %.1fs", n, total_s)
    logger.info("status distribution  : %s", dict(status_counts))
    logger.info("decision distribution: %s", dict(decision_counts))

    return final
