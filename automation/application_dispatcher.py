"""
application_dispatcher.py
-------------------------
Outbound application dispatcher with idempotency.

Modes:
- simulate: log-only dispatch
- email: send via SMTP helper when enabled
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from auto_apply.email_sender import send_email

logger = logging.getLogger("automation.application_dispatcher")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

_AUTOMATION_DIR = Path(__file__).resolve().parent
APPLIED_JOBS_PATH = _AUTOMATION_DIR / "applied_jobs.json"
_APPLIED_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(job: dict) -> str:
    job_id = str(job.get("id", "") or job.get("job_id", "")).strip()
    company = str(job.get("company", "")).strip()
    raw = f"{job_id}{company}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_already_applied(job: dict) -> bool:
    """
    Return True if this job fingerprint already exists in applied_jobs.json.
    """
    fp = _fingerprint(job)
    with _APPLIED_LOCK:
        state = _load_applied_unlocked()
        fingerprints = set(state.get("fingerprints", []))
        return fp in fingerprints


def _load_applied_unlocked() -> dict:
    if not APPLIED_JOBS_PATH.exists():
        return {"fingerprints": []}
    try:
        with open(APPLIED_JOBS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"fingerprints": []}
        fps = data.get("fingerprints", [])
        if not isinstance(fps, list):
            fps = []
        return {"fingerprints": fps}
    except (OSError, json.JSONDecodeError, TypeError):
        return {"fingerprints": []}


def _save_applied_unlocked(state: dict) -> None:
    APPLIED_JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(APPLIED_JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def apply_job(job: dict, mode: str = "simulate") -> dict:
    """
    Dispatch a job application in the given mode.

    Returns:
    {
      "status": "sent|failed|skipped_duplicate",
      "method": "simulate|email",
      "timestamp": "<iso-utc>",
      "reason": "<optional>"
    }
    """
    ts = _utc_now_iso()
    method = (mode or "simulate").strip().lower()
    if method not in {"simulate", "email"}:
        method = "simulate"

    fp = _fingerprint(job)
    with _APPLIED_LOCK:
        state = _load_applied_unlocked()
        fingerprints = set(state.get("fingerprints", []))
        if fp in fingerprints:
            logger.info("[APPLY] duplicate skipped for '%s' at '%s'", job.get("title"), job.get("company"))
            return {
                "status": "skipped_duplicate",
                "method": method,
                "timestamp": ts,
                "reason": "already_applied",
            }

        try:
            if method == "simulate":
                logger.info("[APPLY] simulate sent for '%s' at '%s'", job.get("title"), job.get("company"))
            else:
                enabled = os.getenv("APPLICATION_EMAIL_ENABLED", "false").lower() == "true"
                if not enabled:
                    logger.warning("[APPLY] email mode disabled; falling back to simulate")
                    method = "simulate"
                    logger.info("[APPLY] simulate sent for '%s' at '%s'", job.get("title"), job.get("company"))
                else:
                    payload = {
                        "cover_letter": job.get("cover_letter") or "Please consider my application.",
                        "resume_text": job.get("resume_text") or "Resume not provided.",
                    }
                    if not job.get("apply_email"):
                        return {
                            "status": "failed",
                            "method": "email",
                            "timestamp": ts,
                            "reason": "missing_apply_email",
                        }
                    send_email(job, payload)
                    logger.info("[APPLY] email sent for '%s' at '%s'", job.get("title"), job.get("company"))

            fingerprints.add(fp)
            _save_applied_unlocked({"fingerprints": sorted(fingerprints), "last_updated": ts})
            return {"status": "sent", "method": method, "timestamp": ts}
        except Exception as exc:
            logger.error("[APPLY] failed for '%s' at '%s': %s", job.get("title"), job.get("company"), exc)
            return {
                "status": "failed",
                "method": method,
                "timestamp": ts,
                "reason": str(exc),
            }
