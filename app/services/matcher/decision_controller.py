"""
decision_controller.py
----------------------
Decision Controller — stateless post-processing layer for the v2 structured
match scorer.

Consumes the already-computed ``ScoringResult`` (from ``scorer_v2.py``) and
``ParsedJD`` (from ``jd_parser.py``) and applies four sequential filter layers
to produce a final application decision (``APPLY``, ``SKIP``, or ``REVIEW``),
a human-readable reason, and a priority score for batch ranking.

This module is purely additive: it does NOT modify ``scorer_v2.py``,
``matcher.py``, or ``jd_parser.py``.

Public API
----------
    decision_controller(match_result, job_data, config) -> DecisionResult
    select_top_applications(decisions, max_n) -> list[DecisionResult]

Filter Layer Pipeline
---------------------
    Layer 1 — Score Tier:
        HIGH   → APPLY  (no short-circuit)
        MEDIUM → REVIEW (no short-circuit)
        LOW    → SKIP   (no short-circuit)
        REJECT → SKIP   (short-circuit — layers 2–4 are skipped)

    Layer 2 — Skill Coverage:
        skill_score < threshold → SKIP  (default threshold = 0.5)
        Only runs when current decision is not already SKIP.

    Layer 3 — Role Strictness:
        role_score == 0.0 → SKIP
        Only runs when current decision is not already SKIP.

    Layer 4 — Experience Risk Downgrade:
        experience_score == 0.0 → downgrade one level (APPLY→REVIEW, REVIEW→SKIP)
        Only runs when current decision is not already SKIP.

Priority Score
--------------
    priority_score = match_result["final_score"]  (passthrough, unconditional)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

# Type references only — not called at runtime
if TYPE_CHECKING:
    from app.services.matcher.scorer_v2 import BreakdownDict, ScoringResult


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

class DecisionResult(TypedDict):
    final_decision: str    # "APPLY" | "SKIP" | "REVIEW"
    reason:         str    # non-empty human-readable explanation
    priority_score: float  # == match_result["final_score"], in [0.0, 1.0]


# ---------------------------------------------------------------------------
# Private layer functions
# ---------------------------------------------------------------------------

def _layer1_score_tier(
    score_tier: str,
    final_score: float,
) -> tuple[str, str, bool]:
    """
    Map the v2 score tier to an initial decision.

    Returns
    -------
    (decision, reason, short_circuit)
        ``short_circuit`` is True only for REJECT — callers must skip
        layers 2–4 when it is True.
    """
    if score_tier == "HIGH":
        return (
            "APPLY",
            f"Score tier HIGH (final_score={final_score:.4f}); passed Layer 1.",
            False,
        )
    elif score_tier == "MEDIUM":
        return (
            "REVIEW",
            f"Score tier MEDIUM (final_score={final_score:.4f}); passed Layer 1.",
            False,
        )
    elif score_tier == "LOW":
        return (
            "SKIP",
            (
                f"Score tier is LOW (final_score={final_score:.4f}); "
                "candidate does not meet minimum score threshold."
            ),
            False,
        )
    else:
        # REJECT or any unrecognised tier — treat as REJECT (safe default)
        return (
            "SKIP",
            (
                f"Score tier is REJECT (final_score={final_score:.4f}); "
                "skipping all further layers."
            ),
            True,
        )


def _layer2_skill_coverage(
    decision: str,
    skill_score: float,
    threshold: float,
) -> tuple[str, str]:
    """
    Override decision to SKIP when skill coverage is below the threshold.

    Only called when the current decision is not already SKIP.

    Returns
    -------
    (decision, reason)
    """
    if skill_score < threshold:
        return (
            "SKIP",
            (
                f"Skill coverage {skill_score:.4f} is below threshold "
                f"{threshold:.4f}."
            ),
        )
    return decision, ""


def _layer3_role_strictness(
    decision: str,
    role_score: float,
) -> tuple[str, str]:
    """
    Override decision to SKIP when the role score is exactly 0.0.

    Only called when the current decision is not already SKIP.

    Returns
    -------
    (decision, reason)
    """
    if role_score == 0.0:
        return "SKIP", "Role is a complete mismatch (role_score=0.0)."
    return decision, ""


def _layer4_experience_risk(
    decision: str,
    experience_score: float,
) -> tuple[str, str]:
    """
    Downgrade the decision by one level when experience_score is exactly 0.0.

    Downgrade map:
        APPLY  → REVIEW
        REVIEW → SKIP
        SKIP   → SKIP  (no change — already at floor)

    Only called when the current decision is not already SKIP.

    Returns
    -------
    (decision, reason)
    """
    if experience_score == 0.0:
        if decision == "APPLY":
            new_decision = "REVIEW"
        elif decision == "REVIEW":
            new_decision = "SKIP"
        else:
            # Already SKIP — no change (should not reach here given caller guard,
            # but handled defensively)
            return decision, ""
        return (
            new_decision,
            (
                "Experience level is a significant mismatch "
                f"(experience_score=0.0); decision downgraded from "
                f"{decision} to {new_decision}."
            ),
        )
    return decision, ""


# ---------------------------------------------------------------------------
# Config validation helper
# ---------------------------------------------------------------------------

def _validate_and_get_threshold(config: dict) -> float:
    """
    Extract and validate ``skill_score_threshold`` from *config*.

    Returns the threshold float (default 0.5 when absent).

    Raises
    ------
    ValueError
        If the key is present but is not a float, or is a float outside
        [0.0, 1.0].
    """
    if "skill_score_threshold" not in config:
        return 0.5

    value = config["skill_score_threshold"]

    if not isinstance(value, float):
        raise ValueError(
            f"skill_score_threshold must be a float in [0.0, 1.0], got: {value!r}"
        )

    if not (0.0 <= value <= 1.0):
        raise ValueError(
            f"skill_score_threshold must be in [0.0, 1.0], got: {value}"
        )

    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decision_controller(
    match_result: "ScoringResult",
    job_data: dict,
    config: dict,
) -> DecisionResult:
    """
    Apply four sequential filter layers to produce a final application decision.

    Parameters
    ----------
    match_result : ScoringResult
        Output of ``match_resume_to_job_v2()``.  Must contain:
        - ``final_score`` (float)
        - ``breakdown`` (dict with ``skill``, ``role``, ``experience``)
        - ``decision`` (str: "HIGH" | "MEDIUM" | "LOW" | "REJECT")
    job_data : ParsedJD
        Output of ``parse_job_description()``.  Accepted but not used in
        current filter logic (reserved for future layers).
    config : dict
        Configuration dict.  Recognised keys:
        - ``skill_score_threshold`` (float, default 0.5, must be in [0.0, 1.0])

    Returns
    -------
    DecisionResult
        A TypedDict with keys:
        - ``final_decision`` — "APPLY" | "SKIP" | "REVIEW"
        - ``reason``         — non-empty human-readable explanation
        - ``priority_score`` — equal to ``match_result["final_score"]``

    Raises
    ------
    ValueError
        If ``config["skill_score_threshold"]`` is present but not a float
        in [0.0, 1.0].

    Notes
    -----
    - Does NOT call ``match_resume_to_job_v2()`` or ``parse_job_description()``.
    - Does NOT modify ``match_result`` or ``job_data``.
    - Stateless: no module-level mutable state; safe to call concurrently.
    """
    # --- Config validation (raises ValueError on bad threshold) ---
    threshold = _validate_and_get_threshold(config)

    # --- Priority score: unconditional passthrough ---
    priority_score: float = match_result["final_score"]

    # --- Extract sub-scores ---
    breakdown = match_result["breakdown"]
    skill_score:      float = breakdown["skill"]
    role_score:       float = breakdown["role"]
    experience_score: float = breakdown["experience"]
    score_tier:       str   = match_result["decision"]

    # --- Layer 1: Score Tier ---
    decision, reason, short_circuit = _layer1_score_tier(score_tier, priority_score)

    if short_circuit:
        # REJECT: skip layers 2–4
        return DecisionResult(
            final_decision=decision,
            reason=reason,
            priority_score=priority_score,
        )

    # Track whether Layer 4 produced a downgrade reason
    layer4_reason: str = ""

    # --- Layer 2: Skill Coverage (only when not already SKIP) ---
    if decision != "SKIP":
        new_decision, new_reason = _layer2_skill_coverage(
            decision, skill_score, threshold
        )
        if new_decision == "SKIP":
            return DecisionResult(
                final_decision=new_decision,
                reason=new_reason,
                priority_score=priority_score,
            )

    # --- Layer 3: Role Strictness (only when not already SKIP) ---
    if decision != "SKIP":
        new_decision, new_reason = _layer3_role_strictness(decision, role_score)
        if new_decision == "SKIP":
            return DecisionResult(
                final_decision=new_decision,
                reason=new_reason,
                priority_score=priority_score,
            )

    # --- Layer 4: Experience Risk Downgrade (only when not already SKIP) ---
    if decision != "SKIP":
        new_decision, new_reason = _layer4_experience_risk(decision, experience_score)
        if new_reason:
            # Layer 4 triggered a downgrade — update decision and reason
            decision = new_decision
            layer4_reason = new_reason

    # --- Final output ---
    # Determine the final reason string:
    #   - Layer 4 downgrade: use the downgrade reason
    #   - APPLY (survived all layers): use a clean "passed all layers" message
    #   - SKIP from Layer 1 LOW: use the Layer 1 reason (already set)
    #   - REVIEW from Layer 1 MEDIUM (no downgrade): use the Layer 1 reason
    if layer4_reason:
        final_reason = layer4_reason
    elif decision == "APPLY":
        final_reason = "Score tier HIGH; passed all filter layers."
    else:
        # SKIP (LOW) or REVIEW (MEDIUM) — use the Layer 1 reason
        final_reason = reason

    return DecisionResult(
        final_decision=decision,
        reason=final_reason,
        priority_score=priority_score,
    )


def select_top_applications(
    decisions: list[DecisionResult],
    max_n: int,
) -> list[DecisionResult]:
    """
    Filter, sort, and truncate a list of decision results.

    Returns at most ``max_n`` entries where ``final_decision == "APPLY"``,
    sorted by ``priority_score`` descending.

    Parameters
    ----------
    decisions : list[DecisionResult]
        List of dicts as returned by ``decision_controller()``.
    max_n : int
        Maximum number of entries to return.  Negative values return ``[]``.

    Returns
    -------
    list[DecisionResult]
        New list; input dicts are not modified.
    """
    if max_n < 0:
        return []

    apply_only = [d for d in decisions if d["final_decision"] == "APPLY"]
    sorted_apply = sorted(apply_only, key=lambda d: d["priority_score"], reverse=True)
    return sorted_apply[:max_n]
