"""
rate_controller.py
------------------
Simple persisted rate-control guard for outbound job applications.

State is persisted to automation/rate_state.json and is safe for
multi-threaded access within this process.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_AUTOMATION_DIR = Path(__file__).resolve().parent
RATE_STATE_PATH = _AUTOMATION_DIR / "rate_state.json"

_STATE_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key(now: datetime) -> str:
    return now.date().isoformat()


def _default_state() -> dict:
    return {
        "day": _today_key(_utc_now()),
        "applied_today": 0,
        "last_applied_at": None,
    }


def _load_state_unlocked() -> dict:
    if not RATE_STATE_PATH.exists():
        return _default_state()
    try:
        with open(RATE_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_state()
        merged = _default_state()
        merged.update(data)
        return merged
    except (OSError, json.JSONDecodeError, TypeError):
        return _default_state()


def _save_state_unlocked(state: dict) -> None:
    RATE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RATE_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _maybe_roll_day(state: dict, now: datetime) -> dict:
    today = _today_key(now)
    if state.get("day") != today:
        state["day"] = today
        state["applied_today"] = 0
        state["last_applied_at"] = None
    return state


def check_rate_limit(
    max_applications_per_day: int,
    cooldown_between_applications: int,
) -> tuple[bool, str | None]:
    """
    Returns (allowed, reason_if_blocked).
    """
    now = _utc_now()
    with _STATE_LOCK:
        state = _maybe_roll_day(_load_state_unlocked(), now)

        applied_today = int(state.get("applied_today", 0))
        if applied_today >= max_applications_per_day:
            return False, "daily_limit_reached"

        last_applied_at = state.get("last_applied_at")
        if last_applied_at:
            try:
                last_dt = datetime.fromisoformat(last_applied_at)
                elapsed = (now - last_dt).total_seconds()
                if elapsed < cooldown_between_applications:
                    return False, "cooldown_active"
            except Exception:
                # Corrupt timestamps should not block pipeline.
                pass

        return True, None


def record_application() -> None:
    """
    Record one successful application attempt into persisted state.
    """
    now = _utc_now()
    with _STATE_LOCK:
        state = _maybe_roll_day(_load_state_unlocked(), now)
        state["applied_today"] = int(state.get("applied_today", 0)) + 1
        state["last_applied_at"] = now.isoformat()
        _save_state_unlocked(state)

