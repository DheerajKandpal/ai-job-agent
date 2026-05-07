"""
metrics_collector.py
--------------------
Run-level metrics computation and persistence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_AUTOMATION_DIR = Path(__file__).resolve().parent
METRICS_PATH = _AUTOMATION_DIR / "metrics.json"


def build_metrics(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_jobs_processed": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "avg_processing_time": 0.0,
            "llm_success": 0,
            "llm_fallback": 0,
        }

    success_statuses = {"completed", "logged", "rejected"}
    success_count = sum(1 for r in results if r.get("status") in success_statuses)
    failure_count = total - success_count
    avg_processing = round(
        sum(float(r.get("duration_s", 0.0)) for r in results) / total,
        2,
    )

    llm_success = sum(1 for r in results if r.get("decision") is not None)
    llm_fallback = sum(
        1
        for r in results
        if r.get("failed_at") in {"match", "tailor", "cover-letter"}
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_jobs_processed": total,
        "success_rate": round((success_count / total) * 100.0, 2),
        "failure_rate": round((failure_count / total) * 100.0, 2),
        "avg_processing_time": avg_processing,
        "llm_success": llm_success,
        "llm_fallback": llm_fallback,
    }


def save_metrics(metrics: dict) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)

