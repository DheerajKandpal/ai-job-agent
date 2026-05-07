"""
feedback_analyzer.py
--------------------
Builds aggregate application-outcome feedback metrics.
"""

from __future__ import annotations

from app.services.tracker.db_service import _get_connection


def _score_bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 0.5:
        return "0.00-0.49"
    if score < 0.7:
        return "0.50-0.69"
    if score < 0.85:
        return "0.70-0.84"
    return "0.85-1.00"


def get_feedback_report() -> dict:
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    job_title,
                    match_score,
                    outcome_status,
                    applied_at,
                    first_response_at
                FROM applications
                """
            )
            rows = cur.fetchall()
    finally:
        if conn is not None:
            conn.close()

    total = len(rows)
    if total == 0:
        return {
            "success_rate": 0.0,
            "avg_response_time_hours": None,
            "best_performing_roles": [],
            "score_ranges_vs_outcomes": {},
            "total_applications": 0,
        }

    interview_count = 0
    response_hours: list[float] = []
    role_totals: dict[str, int] = {}
    role_interviews: dict[str, int] = {}
    score_ranges_vs_outcomes: dict[str, dict[str, int]] = {}

    for _, job_title, match_score, outcome_status, applied_at, first_response_at in rows:
        role_totals[job_title] = role_totals.get(job_title, 0) + 1
        if outcome_status == "interview":
            interview_count += 1
            role_interviews[job_title] = role_interviews.get(job_title, 0) + 1

        if applied_at and first_response_at:
            response_hours.append(
                round((first_response_at - applied_at).total_seconds() / 3600.0, 2)
            )

        bucket = _score_bucket(match_score)
        if bucket not in score_ranges_vs_outcomes:
            score_ranges_vs_outcomes[bucket] = {}
        outcomes = score_ranges_vs_outcomes[bucket]
        outcomes[outcome_status] = outcomes.get(outcome_status, 0) + 1

    success_rate = round((interview_count / total) * 100.0, 2)
    avg_response_time = (
        round(sum(response_hours) / len(response_hours), 2) if response_hours else None
    )

    role_rows = []
    for role, count in role_totals.items():
        interviews = role_interviews.get(role, 0)
        role_rows.append(
            {
                "role": role,
                "applications": count,
                "interviews": interviews,
                "interview_rate": round((interviews / count) * 100.0, 2),
            }
        )
    role_rows.sort(
        key=lambda r: (r["interview_rate"], r["interviews"], r["applications"]),
        reverse=True,
    )

    return {
        "success_rate": success_rate,
        "avg_response_time_hours": avg_response_time,
        "best_performing_roles": role_rows[:5],
        "score_ranges_vs_outcomes": score_ranges_vs_outcomes,
        "total_applications": total,
    }

