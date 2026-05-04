"""
Example-based (unit) tests for decision_controller.py.

Covers:
- All 5 representative cases from Requirement 12
- Default threshold behaviour
- select_top_applications() edge cases
- Reason string content spot-checks
- V2 scorer non-regression (scorer_v2 still importable and callable)
"""

from __future__ import annotations

import pytest

from app.services.matcher.decision_controller import (
    DecisionResult,
    decision_controller,
    select_top_applications,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_match_result(
    decision: str,
    final_score: float,
    skill: float,
    role: float,
    experience: float,
    tools: float = 0.8,
    keywords: float = 0.3,
) -> dict:
    return {
        "final_score": final_score,
        "breakdown": {
            "skill": skill,
            "role": role,
            "experience": experience,
            "tools": tools,
            "keywords": keywords,
        },
        "decision": decision,
    }


def _make_apply_result(priority_score: float) -> dict:
    return {"final_decision": "APPLY", "reason": "passed", "priority_score": priority_score}


def _make_skip_result(priority_score: float) -> dict:
    return {"final_decision": "SKIP", "reason": "skipped", "priority_score": priority_score}


def _make_review_result(priority_score: float) -> dict:
    return {"final_decision": "REVIEW", "reason": "review", "priority_score": priority_score}


# ---------------------------------------------------------------------------
# Task 6.1 — Five representative cases from Requirement 12
# ---------------------------------------------------------------------------

class TestRequirement12Cases:
    """All five representative cases from Requirement 12."""

    def test_case_1_clean_apply(self):
        """
        Req 12.1: HIGH + all sub-scores above threshold → APPLY.
        Layer 1: HIGH → APPLY
        Layer 2: skill 0.80 >= 0.50 → no change
        Layer 3: role 1.0 > 0.0 → no change
        Layer 4: experience 1.0 > 0.0 → no change
        """
        match_result = _make_match_result("HIGH", 0.82, skill=0.80, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})

        assert result["final_decision"] == "APPLY"
        assert result["priority_score"] == 0.82
        assert len(result["reason"]) > 0

    def test_case_2_skill_coverage_override(self):
        """
        Req 12.2: MEDIUM + skill < 0.5 → SKIP via Layer 2.
        Layer 1: MEDIUM → REVIEW
        Layer 2: skill 0.30 < 0.50 → SKIP (short-circuit)
        """
        match_result = _make_match_result("MEDIUM", 0.55, skill=0.30, role=0.6, experience=0.5)
        result = decision_controller(match_result, {}, {})

        assert result["final_decision"] == "SKIP"
        assert result["priority_score"] == 0.55

    def test_case_3_role_mismatch_override(self):
        """
        Req 12.3: HIGH + role == 0.0 → SKIP via Layer 3.
        Layer 1: HIGH → APPLY
        Layer 2: skill 0.80 >= 0.50 → no change
        Layer 3: role 0.0 == 0.0 → SKIP (short-circuit)
        """
        match_result = _make_match_result("HIGH", 0.74, skill=0.80, role=0.0, experience=1.0)
        result = decision_controller(match_result, {}, {})

        assert result["final_decision"] == "SKIP"
        assert result["priority_score"] == 0.74

    def test_case_4_experience_risk_downgrade(self):
        """
        Req 12.4: HIGH + experience == 0.0 → REVIEW via Layer 4 downgrade.
        Layer 1: HIGH → APPLY
        Layer 2: skill 0.80 >= 0.50 → no change
        Layer 3: role 1.0 > 0.0 → no change
        Layer 4: experience 0.0 == 0.0, APPLY → REVIEW
        """
        match_result = _make_match_result("HIGH", 0.71, skill=0.80, role=1.0, experience=0.0)
        result = decision_controller(match_result, {}, {})

        assert result["final_decision"] == "REVIEW"
        assert result["priority_score"] == 0.71

    def test_case_5_low_score_tier(self):
        """
        Req 12.5: LOW → SKIP via Layer 1 (no short-circuit, layers 2–4 still run
        but cannot change SKIP to non-SKIP).
        """
        match_result = _make_match_result("LOW", 0.30, skill=0.60, role=0.6, experience=1.0)
        result = decision_controller(match_result, {}, {})

        assert result["final_decision"] == "SKIP"
        assert result["priority_score"] == 0.30


# ---------------------------------------------------------------------------
# Task 6.2 — Default threshold behaviour and config edge cases
# ---------------------------------------------------------------------------

class TestDefaultThresholdAndConfig:
    """Default threshold behaviour and config edge cases."""

    def test_default_threshold_skill_below_causes_skip(self):
        """
        config={} with skill=0.4 → SKIP from Layer 2 (default threshold 0.5).
        """
        match_result = _make_match_result("HIGH", 0.75, skill=0.4, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "SKIP"

    def test_default_threshold_skill_above_passes_layer2(self):
        """
        config={} with skill=0.6 → Layer 2 does not trigger SKIP.
        """
        match_result = _make_match_result("HIGH", 0.80, skill=0.6, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        # Layer 2 should not have triggered; result should be APPLY
        assert result["final_decision"] == "APPLY"

    def test_default_threshold_skill_exactly_at_threshold_passes(self):
        """
        skill == 0.5 (exactly at default threshold) → Layer 2 does NOT trigger
        (condition is strictly less than).
        """
        match_result = _make_match_result("HIGH", 0.80, skill=0.5, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "APPLY"

    def test_max_applications_per_run_absent_no_error(self):
        """
        max_applications_per_run absent from config → no error raised.
        """
        match_result = _make_match_result("HIGH", 0.80, skill=0.8, role=1.0, experience=1.0)
        # Should not raise
        result = decision_controller(match_result, {}, {"max_applications_per_run": 5})
        assert result["final_decision"] == "APPLY"

    def test_empty_config_no_error(self):
        """config={} is valid and uses all defaults."""
        match_result = _make_match_result("MEDIUM", 0.50, skill=0.6, role=0.6, experience=0.5)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] in {"APPLY", "SKIP", "REVIEW"}

    def test_explicit_threshold_zero_point_three(self):
        """
        Explicit threshold=0.3: skill=0.25 → SKIP; skill=0.35 → not SKIP from Layer 2.
        """
        base = _make_match_result("HIGH", 0.75, skill=0.25, role=1.0, experience=1.0)
        result = decision_controller(base, {}, {"skill_score_threshold": 0.3})
        assert result["final_decision"] == "SKIP"

        above = _make_match_result("HIGH", 0.75, skill=0.35, role=1.0, experience=1.0)
        result2 = decision_controller(above, {}, {"skill_score_threshold": 0.3})
        assert result2["final_decision"] == "APPLY"


# ---------------------------------------------------------------------------
# Task 6.3 — select_top_applications() edge cases
# ---------------------------------------------------------------------------

class TestSelectTopApplications:
    """Edge cases for select_top_applications()."""

    def test_empty_list_returns_empty(self):
        """Empty input → empty output."""
        assert select_top_applications([], 5) == []

    def test_all_skip_returns_empty(self):
        """All SKIP decisions → no APPLY → empty output."""
        decisions = [_make_skip_result(0.8), _make_skip_result(0.6)]
        assert select_top_applications(decisions, 5) == []

    def test_all_review_returns_empty(self):
        """All REVIEW decisions → no APPLY → empty output."""
        decisions = [_make_review_result(0.7), _make_review_result(0.5)]
        assert select_top_applications(decisions, 5) == []

    def test_fewer_apply_than_max_n_returns_all_apply(self):
        """2 APPLY decisions with max_n=10 → returns both."""
        decisions = [
            _make_apply_result(0.9),
            _make_apply_result(0.7),
            _make_skip_result(0.8),
        ]
        result = select_top_applications(decisions, 10)
        assert len(result) == 2
        assert all(d["final_decision"] == "APPLY" for d in result)

    def test_more_apply_than_max_n_truncates(self):
        """5 APPLY decisions with max_n=3 → returns top 3 by priority_score."""
        decisions = [
            _make_apply_result(0.5),
            _make_apply_result(0.9),
            _make_apply_result(0.7),
            _make_apply_result(0.3),
            _make_apply_result(0.8),
        ]
        result = select_top_applications(decisions, 3)
        assert len(result) == 3
        assert [d["priority_score"] for d in result] == [0.9, 0.8, 0.7]

    def test_sorted_descending_by_priority_score(self):
        """Results are sorted by priority_score descending."""
        decisions = [
            _make_apply_result(0.4),
            _make_apply_result(0.9),
            _make_apply_result(0.6),
        ]
        result = select_top_applications(decisions, 10)
        scores = [d["priority_score"] for d in result]
        assert scores == sorted(scores, reverse=True)

    def test_negative_max_n_returns_empty(self):
        """Negative max_n → empty list."""
        decisions = [_make_apply_result(0.9), _make_apply_result(0.8)]
        assert select_top_applications(decisions, -1) == []
        assert select_top_applications(decisions, -100) == []

    def test_max_n_zero_returns_empty(self):
        """max_n=0 → empty list even with APPLY decisions."""
        decisions = [_make_apply_result(0.9)]
        assert select_top_applications(decisions, 0) == []

    def test_input_dicts_not_modified(self):
        """Input dicts are not modified by select_top_applications()."""
        import copy
        decisions = [_make_apply_result(0.9), _make_skip_result(0.5)]
        original = copy.deepcopy(decisions)
        select_top_applications(decisions, 5)
        assert decisions == original

    def test_mixed_decisions_only_apply_returned(self):
        """Mixed APPLY/SKIP/REVIEW → only APPLY in output."""
        decisions = [
            _make_apply_result(0.9),
            _make_skip_result(0.95),   # higher score but SKIP
            _make_review_result(0.85), # higher score but REVIEW
            _make_apply_result(0.7),
        ]
        result = select_top_applications(decisions, 10)
        assert len(result) == 2
        assert all(d["final_decision"] == "APPLY" for d in result)


# ---------------------------------------------------------------------------
# Task 6.4 — Reason string content spot-checks
# ---------------------------------------------------------------------------

class TestReasonStringContent:
    """Spot-check reason string content for each layer trigger."""

    def test_apply_reason_mentions_score_tier(self):
        """APPLY reason mentions HIGH score tier."""
        match_result = _make_match_result("HIGH", 0.82, skill=0.80, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "APPLY"
        assert "HIGH" in result["reason"]

    def test_layer2_skip_reason_contains_skill_score_and_threshold(self):
        """Layer 2 SKIP reason contains the skill score and threshold values."""
        match_result = _make_match_result("HIGH", 0.75, skill=0.30, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {"skill_score_threshold": 0.5})
        assert result["final_decision"] == "SKIP"
        assert "0.3000" in result["reason"]
        assert "0.5000" in result["reason"]

    def test_layer3_skip_reason_mentions_role_mismatch(self):
        """Layer 3 SKIP reason mentions role mismatch."""
        match_result = _make_match_result("HIGH", 0.74, skill=0.80, role=0.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "SKIP"
        assert "role" in result["reason"].lower()
        assert "mismatch" in result["reason"].lower()

    def test_layer4_downgrade_reason_mentions_experience_and_old_new_decision(self):
        """Layer 4 downgrade reason mentions experience_score and old/new decision."""
        match_result = _make_match_result("HIGH", 0.71, skill=0.80, role=1.0, experience=0.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "REVIEW"
        assert "experience_score=0.0" in result["reason"]
        assert "APPLY" in result["reason"]
        assert "REVIEW" in result["reason"]

    def test_layer4_review_to_skip_reason_mentions_downgrade(self):
        """Layer 4 REVIEW→SKIP downgrade reason mentions both decisions."""
        match_result = _make_match_result("MEDIUM", 0.50, skill=0.80, role=1.0, experience=0.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "SKIP"
        assert "experience_score=0.0" in result["reason"]
        assert "REVIEW" in result["reason"]
        assert "SKIP" in result["reason"]

    def test_reject_reason_mentions_reject_tier(self):
        """REJECT short-circuit reason mentions REJECT."""
        match_result = _make_match_result("REJECT", 0.10, skill=0.80, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "SKIP"
        assert "REJECT" in result["reason"]

    def test_low_reason_mentions_low_tier(self):
        """LOW tier reason mentions LOW."""
        match_result = _make_match_result("LOW", 0.30, skill=0.80, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "SKIP"
        assert "LOW" in result["reason"]

    def test_medium_review_reason_mentions_medium(self):
        """MEDIUM tier that survives all layers → REVIEW reason mentions MEDIUM."""
        match_result = _make_match_result("MEDIUM", 0.50, skill=0.80, role=1.0, experience=1.0)
        result = decision_controller(match_result, {}, {})
        assert result["final_decision"] == "REVIEW"
        assert "MEDIUM" in result["reason"]


# ---------------------------------------------------------------------------
# Task 6.5 — V2 scorer non-regression
# ---------------------------------------------------------------------------

class TestScorerV2NonRegression:
    """Verify scorer_v2 is still importable and callable after this feature."""

    def test_scorer_v2_importable(self):
        """scorer_v2 module is importable."""
        import app.services.matcher.scorer_v2 as scorer_v2  # noqa: F401
        assert hasattr(scorer_v2, "match_resume_to_job_v2")

    def test_scorer_v2_callable(self):
        """match_resume_to_job_v2 is callable and returns expected structure."""
        from app.services.matcher.scorer_v2 import match_resume_to_job_v2

        result = match_resume_to_job_v2(
            resume_text="Senior Data Scientist with Python, SQL, machine learning.",
            job_description="Senior Data Scientist — Python, SQL, machine learning. 5+ years.",
        )

        assert "final_score" in result
        assert "breakdown" in result
        assert "decision" in result
        assert isinstance(result["final_score"], float)
        assert result["decision"] in {"HIGH", "MEDIUM", "LOW", "REJECT"}

    def test_scorer_v2_result_feeds_decision_controller(self):
        """
        End-to-end: scorer_v2 output can be passed directly to decision_controller.
        """
        from app.services.matcher.scorer_v2 import match_resume_to_job_v2

        scoring_result = match_resume_to_job_v2(
            resume_text="Senior Data Scientist with Python, SQL, machine learning, TensorFlow.",
            job_description="Senior Data Scientist — Python, SQL, machine learning. 5+ years.",
        )

        dc_result = decision_controller(scoring_result, {}, {})

        assert dc_result["final_decision"] in {"APPLY", "SKIP", "REVIEW"}
        assert dc_result["priority_score"] == scoring_result["final_score"]
        assert len(dc_result["reason"]) > 0


# ---------------------------------------------------------------------------
# Config validation error cases
# ---------------------------------------------------------------------------

class TestConfigValidation:
    """ValueError raised for invalid skill_score_threshold."""

    def test_threshold_negative_raises_value_error(self):
        match_result = _make_match_result("HIGH", 0.8, 0.8, 1.0, 1.0)
        with pytest.raises(ValueError, match="skill_score_threshold"):
            decision_controller(match_result, {}, {"skill_score_threshold": -0.1})

    def test_threshold_above_one_raises_value_error(self):
        match_result = _make_match_result("HIGH", 0.8, 0.8, 1.0, 1.0)
        with pytest.raises(ValueError, match="skill_score_threshold"):
            decision_controller(match_result, {}, {"skill_score_threshold": 1.1})

    def test_threshold_string_raises_value_error(self):
        match_result = _make_match_result("HIGH", 0.8, 0.8, 1.0, 1.0)
        with pytest.raises(ValueError, match="skill_score_threshold"):
            decision_controller(match_result, {}, {"skill_score_threshold": "0.5"})

    def test_threshold_int_raises_value_error(self):
        """int is not a float — should raise ValueError."""
        match_result = _make_match_result("HIGH", 0.8, 0.8, 1.0, 1.0)
        with pytest.raises(ValueError, match="skill_score_threshold"):
            decision_controller(match_result, {}, {"skill_score_threshold": 1})

    def test_threshold_none_raises_value_error(self):
        match_result = _make_match_result("HIGH", 0.8, 0.8, 1.0, 1.0)
        with pytest.raises(ValueError, match="skill_score_threshold"):
            decision_controller(match_result, {}, {"skill_score_threshold": None})

    def test_threshold_zero_is_valid(self):
        """0.0 is a valid threshold (edge of range)."""
        match_result = _make_match_result("HIGH", 0.8, 0.0, 1.0, 1.0)
        # skill=0.0 < threshold=0.0 is False (not strictly less), so no SKIP from Layer 2
        result = decision_controller(match_result, {}, {"skill_score_threshold": 0.0})
        assert result["final_decision"] in {"APPLY", "SKIP", "REVIEW"}

    def test_threshold_one_is_valid(self):
        """1.0 is a valid threshold (edge of range)."""
        match_result = _make_match_result("HIGH", 0.8, 0.8, 1.0, 1.0)
        # skill=0.8 < 1.0 → SKIP from Layer 2
        result = decision_controller(match_result, {}, {"skill_score_threshold": 1.0})
        assert result["final_decision"] == "SKIP"
