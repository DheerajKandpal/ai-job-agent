"""
feedback_logger.py — Append-only JSONL logger for job application outcomes.

Public interface
----------------
log_job_result(job, score, tier, applied)
    Append one JSON record to auto_apply/job_logs.jsonl.
    Prints [ERROR] on I/O failure — never interrupts the pipeline.
"""

import json
import os

# Path is relative to the module file so it works from any working directory.
_LOG_FILE = os.path.join(os.path.dirname(__file__), "job_logs.jsonl")


def log_job_result(job: dict, score: float, tier: str, applied: bool) -> None:
    """
    Append one JSONL record describing the outcome of a single job.

    Args:
        job:     The job dict processed by the runner.
        score:   The float score returned by score_job().
        tier:    The tier string returned by classify_job() ("high"/"medium"/"low").
        applied: True if the application was successfully delivered, False otherwise.

    The record written to disk:
        {"id": ..., "title": ..., "company": ..., "score": ..., "tier": ..., "applied": ...}

    On failure, prints [ERROR] and returns — never raises.
    """
    record = {
        "id":      job.get("id", "unknown"),
        "title":   job.get("title", ""),
        "company": job.get("company", ""),
        "score":   score,
        "tier":    tier,
        "applied": applied,
    }
    try:
        # Serialise first so a TypeError never produces a partial write.
        line = json.dumps(record) + "\n"
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line)
    except (OSError, TypeError, ValueError) as exc:
        print(f"[ERROR] Failed to log job result: {exc}")
