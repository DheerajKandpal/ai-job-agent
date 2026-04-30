"""
runner.py — Orchestrates the autonomous job application pipeline.

For each job in the provided list the runner:
  1. Validates required environment variables.
  2. Checks the per-run job cap via should_continue().
  3. Scores and classifies the job; skips low/medium tiers.
  4. Calls POST /tailor to get a tailored resume.
  5. Calls POST /cover-letter to generate a cover letter.
  6. Extracts plain strings from the API responses.
  7. Passes both strings to the Formatter.
  8. Validates email config before email delivery; falls back to endpoint.
  9. Delegates to the appropriate sender with one automatic retry on failure.
  10. On successful delivery, PATCHes /applications/{job_id} to mark the job as applied.
  11. Logs every outcome via feedback_logger.
  12. Waits between jobs using the rate limiter.
"""

import os
from typing import Callable

import requests

from auto_apply.email_sender import send_email
from auto_apply.endpoint_sender import send_to_endpoint
from auto_apply.formatter import format_application
from auto_apply.rate_limiter import should_continue, wait
from auto_apply.scorer import score_job, THRESHOLD, classify_job
from auto_apply.feedback_logger import log_job_result

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL: str = os.getenv("BASE_URL", "http://127.0.0.1:8000")
API_KEY: str | None = os.getenv("API_KEY")

_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
}

_EMAIL_ENV_VARS: tuple[str, ...] = ("EMAIL_HOST", "EMAIL_PORT", "EMAIL_USER", "EMAIL_PASS")


def _get_headers() -> dict[str, str]:
    """Return request headers with the current API_KEY injected."""
    return {**_HEADERS, "Authorization": f"Bearer {API_KEY}"}


def _email_config_valid() -> bool:
    """Return True only if all required email environment variables are set."""
    return all(os.getenv(var) for var in _EMAIL_ENV_VARS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _post(endpoint: str, payload: dict, step: str, job_id: str) -> dict | None:
    """
    Send a POST request to the given endpoint.

    Returns the parsed JSON dict on success, or None on any failure.
    Logs errors but does not raise — callers should check for None and skip.
    """
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=60)
    except requests.RequestException as exc:
        print(f"[ERROR] [{job_id}] {step} network error: {exc}")
        return None

    if response.status_code != 200:
        print(f"[ERROR] [{job_id}] {step} failed (HTTP {response.status_code}): {response.text}")
        return None

    try:
        return response.json()
    except ValueError as exc:
        print(f"[ERROR] [{job_id}] {step} JSON parse error: {exc}")
        return None


def _send_with_retry(sender_fn: Callable, job: dict, payload: dict) -> bool:
    """
    Call sender_fn(job, payload), retrying once on exception.

    On first failure: logs "Retrying..." and retries.
    On second failure: logs the error and returns False.

    Returns:
        True  — sender succeeded (first attempt or retry).
        False — sender failed on both attempts.
    """
    try:
        sender_fn(job, payload)
        return True
    except Exception:
        print("[INFO] Retrying...")
        try:
            sender_fn(job, payload)
            return True
        except Exception as exc:
            print(f"[ERROR] [{job.get('id', 'unknown')}] sender failed after retry: {exc}")
            return False


def update_application_status(job_id: str) -> None:
    """
    PATCH /applications/{job_id} to mark the application as 'applied'.

    Logs progress and swallows failures so the pipeline is never interrupted.

    Args:
        job_id: The unique identifier of the job that was successfully applied to.
    """
    print(f"[INFO] Updating status for job: {job_id}")
    url = f"{BASE_URL}/applications/{job_id}"
    try:
        response = requests.patch(
            url,
            headers=_get_headers(),
            json={"status": "applied"},
            timeout=60,
        )
        if response.status_code not in (200, 204):
            print(
                f"[ERROR] Failed to update status"
                f" (HTTP {response.status_code}): {response.text}"
            )
            return
        print("[INFO] Status updated")
    except Exception as exc:
        print(f"[ERROR] Failed to update status: {exc}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def process_jobs(jobs: list) -> None:
    """
    Run the autonomous application pipeline for a list of jobs.

    Args:
        jobs: A list of job dicts. Each dict must contain at minimum:
              - 'id'          (str) — unique job identifier, used in logs
              - 'title'       (str) — job title
              - 'company'     (str) — company name
              - 'description' (str) — full job description text
              - 'link'        (str) — URL to the original job posting

              Optional keys:
              - 'apply_email'    (str | None) — if non-empty, use email delivery
              - 'apply_endpoint' (str | None) — if non-empty (and no apply_email), use endpoint delivery

    Raises:
        ValueError: If API_KEY or BASE_URL are not set in the environment.
    """
    # ---------------------------------------------------------------------- #
    # Env validation — fail fast before touching any job
    # ---------------------------------------------------------------------- #
    missing = [var for var in ("API_KEY", "BASE_URL") if not os.getenv(var)]
    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them before starting the pipeline."
        )

    if not jobs:
        print("[INFO] No jobs to process.")
        return

    processed_count: int = 0

    for index, job in enumerate(jobs):
        # ------------------------------------------------------------------ #
        # Rate limit — check job cap before starting each job
        # ------------------------------------------------------------------ #
        if not should_continue(processed_count):
            print("[INFO] Max job limit reached")
            break

        job_id: str = job.get("id", "unknown")
        title: str = job.get("title", "unknown")
        company: str = job.get("company", "")
        description: str = job.get("description", "")

        # ------------------------------------------------------------------ #
        # Score — evaluate job quality before any API calls
        # ------------------------------------------------------------------ #
        score = score_job(job)
        tier = classify_job(score)
        print(f"[INFO] Job score: {score} | Tier: {tier}")
        if tier == "medium":
            print("[INFO] Skipping job - medium priority")
            log_job_result(job, score, tier, applied=False)
            _maybe_wait(index, jobs, processed_count)
            continue
        if tier == "low":
            print("[INFO] Skipping job - low score")
            log_job_result(job, score, tier, applied=False)
            _maybe_wait(index, jobs, processed_count)
            continue

        full_description = f"{title} at {company}\n\n{description}".strip()

        # ------------------------------------------------------------------ #
        # Step 1 — Tailor resume
        # ------------------------------------------------------------------ #
        print(f"[INFO] Processing job: {job_id} | {title}")
        print("[INFO] Tailoring resume...")

        tailor_data = _post(
            "/tailor",
            {"job_description": full_description},
            "tailor",
            job_id,
        )
        if tailor_data is None:
            print(f"[ERROR] Tailor API failed for job: {job_id}")
            log_job_result(job, score, tier, applied=False)
            _maybe_wait(index, jobs, processed_count)
            continue

        # ------------------------------------------------------------------ #
        # Step 2 — Generate cover letter
        # ------------------------------------------------------------------ #
        print("[INFO] Generating cover letter...")

        cover_letter_data = _post(
            "/cover-letter",
            {"job_description": full_description},
            "cover-letter",
            job_id,
        )
        if cover_letter_data is None:
            print(f"[ERROR] Cover letter API failed for job: {job_id}")
            log_job_result(job, score, tier, applied=False)
            _maybe_wait(index, jobs, processed_count)
            continue

        # ------------------------------------------------------------------ #
        # Step 3 — Extract plain strings and format application payload
        # ------------------------------------------------------------------ #
        resume_str = str(tailor_data.get("tailored_resume", tailor_data))
        cover_letter_str = cover_letter_data.get("cover_letter", str(cover_letter_data))
        payload = format_application(resume_str, cover_letter_str)

        # ------------------------------------------------------------------ #
        # Step 4 — Select delivery method and send (with retry)
        # ------------------------------------------------------------------ #
        apply_email: str = job.get("apply_email") or ""
        apply_endpoint: str = job.get("apply_endpoint") or ""

        if apply_email:
            if not _email_config_valid():
                print("[ERROR] Email config missing — skipping email delivery")
                log_job_result(job, score, tier, applied=False)
                _maybe_wait(index, jobs, processed_count)
                continue
            print("[INFO] Applying via: email")
            sent = _send_with_retry(send_email, job, payload)
        elif apply_endpoint:
            print("[INFO] Applying via: endpoint")
            sent = _send_with_retry(send_to_endpoint, job, payload)
        else:
            print("[INFO] Skipping job - no apply method")
            log_job_result(job, score, tier, applied=False)
            _maybe_wait(index, jobs, processed_count)
            continue

        # ------------------------------------------------------------------ #
        # Step 5 — Update application status (only on successful delivery)
        # ------------------------------------------------------------------ #
        if sent:
            update_application_status(job_id)

        # ------------------------------------------------------------------ #
        # Step 6 — Log outcome and mark done
        # ------------------------------------------------------------------ #
        log_job_result(job, score, tier, applied=sent)
        processed_count += 1
        print("[INFO] Completed job")

        _maybe_wait(index, jobs, processed_count)


def _maybe_wait(index: int, jobs: list, processed_count: int) -> None:
    """
    Call wait() between jobs — but not after the last job or when the cap is reached.

    Args:
        index: Current job index (0-based) in the jobs list.
        jobs: The full jobs list.
        processed_count: Number of jobs processed so far (after this job).
    """
    is_last_job = index == len(jobs) - 1
    cap_reached = not should_continue(processed_count)

    if not is_last_job and not cap_reached:
        print("[INFO] Waiting before next job...")
        wait()
