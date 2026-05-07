"""
pipeline_logger.py
------------------
Structured stage logging for the automation pipeline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_AUTOMATION_DIR = Path(__file__).resolve().parent
PIPELINE_LOG_PATH = _AUTOMATION_DIR / "pipeline_logs.jsonl"

logger = logging.getLogger("automation.pipeline_logger")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def log_stage(
    job_id: str | int,
    stage: str,
    status: str,
    duration_ms: int | float,
    error: str | None = None,
) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "stage": stage,
        "status": status,
        "duration_ms": round(float(duration_ms), 2),
        "error": error,
    }
    logger.info("[PIPELINE] %s", json.dumps(payload, default=str))

    PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PIPELINE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")

