"""
outcome_tracker.py
------------------
Tracks application outcomes and maintains structured outcome history.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.tracker.db_service import get_outcome_fields, update_outcome_fields

ALLOWED_OUTCOME_STATUSES = ("applied", "interview", "rejected", "no_response")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_feedback_tags(notes: str | None) -> list[str]:
    if not notes:
        return []
    tags: list[str] = []
    for token in notes.split(","):
        cleaned = token.strip().lower().replace(" ", "_")
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    return tags


def track_application_outcome(application_id: int) -> dict:
    """
    Return current outcome tracking state for a single application.
    """
    row = get_outcome_fields(application_id)
    applied_at = row.get("applied_at")
    first_response_at = row.get("first_response_at")
    response_time_hours = None
    if applied_at and first_response_at:
        response_time_hours = round(
            (first_response_at - applied_at).total_seconds() / 3600.0, 2
        )

    row["response_time_hours"] = response_time_hours
    return row


def update_outcome(application_id: int, status: str, notes: str | None = None) -> dict:
    """
    Update outcome status and append an immutable event into outcome_history.
    """
    if status not in ALLOWED_OUTCOME_STATUSES:
        raise ValueError(
            f"Invalid outcome status: {status}. Allowed: {ALLOWED_OUTCOME_STATUSES}"
        )

    current = get_outcome_fields(application_id)
    now = _now_utc()

    previous_status = current.get("outcome_status") or "applied"
    applied_at = current.get("applied_at") or now
    first_response_at = current.get("first_response_at")

    if (
        previous_status == "applied"
        and status in {"interview", "rejected"}
        and first_response_at is None
    ):
        first_response_at = now

    response_time_hours = None
    if applied_at and first_response_at:
        response_time_hours = round(
            (first_response_at - applied_at).total_seconds() / 3600.0, 2
        )

    history = list(current.get("outcome_history") or [])
    history.append(
        {
            "timestamp": now.isoformat(),
            "from_status": previous_status,
            "to_status": status,
            "notes": notes,
            "response_time_hours": response_time_hours,
        }
    )

    existing_tags = list(current.get("feedback_tags") or [])
    tag_set = {t for t in existing_tags if t}
    for tag in _extract_feedback_tags(notes):
        tag_set.add(tag)
    feedback_tags = sorted(tag_set)

    update_outcome_fields(
        application_id=application_id,
        outcome_status=status,
        outcome_history=history,
        last_outcome_update=now,
        feedback_tags=feedback_tags,
        applied_at=applied_at,
        first_response_at=first_response_at,
    )

    updated = track_application_outcome(application_id)
    updated["previous_status"] = previous_status
    return updated

