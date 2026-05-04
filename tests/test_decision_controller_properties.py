"""
Property-based tests for decision_controller.py using Hypothesis.

Feature: decision-controller
Each test is annotated with the property number it validates.

All 12 properties from the design document are covered here.
"""

from __future__ import annotations

import copy

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.matcher.decision_controller import (
    DecisionResult,
    decision_controller,
    select_top_applications,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Valid score tier values
_SCORE_TIERS = st.sampled_from(["HIGH", "MEDIUM", "LOW", "REJECT"])

# Sub-score in [0.0, 1.0]
_SUB_SCORE = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# final_score in [0.0, 1.0]
_FINAL_SCORE = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Valid threshold in [0.0, 1.0]
_THRESHOLD = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def _make_match_result(
    decision: str,
    final_score: float,
    skill: float,
    role: float,
    experience: float,
    tools: float = 0.5,
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


@st.composite
def valid_match_result(draw) -> dict:
    """Generate a valid ScoringResult-shaped dict."""
    decision = draw(_SCORE_TIERS)
    final_score = draw(_FINAL_SCORE)
    skill = draw(_SUB_SCORE)
    role = draw(_SUB_SCORE)
    experience = draw(_SUB_SCORE)
    tools = draw(_SUB_SCORE)
    keywords = draw(st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False))
    return _make_match_result(decision, final_score, skill, role, experience, tools, keywords)


@st.composite
def valid_config(draw) -> dict:
    """Generate a valid config dict (may or may not include threshold)."""
    include_threshold = draw(st.booleans())
    if include_threshold:
        threshold = draw(_THRESHOLD)
        return {"skill_score_threshold": threshold}
    return {}


@st.composite
def decision_result_dict(draw) -> dict:
    """Generate a DecisionResult-shaped dict for batch function tests."""
    final_decision = draw(st.sampled_from(["APPLY", "SKIP", "REVIEW"]))
    priority_score = draw(_FINAL_SCORE)
    reason = draw(st.text(min_size=1, max_size=100))
    return {
        "final_decision": final_decision,
        "reason": reason,
        "priority_score": priority_score,
    }


# ---------------------------------------------------------------------------
# Property 1: Output Schema Invariant
# Feature: decision-controller, Property 1: Output Schema Invariant
# Validates: Requirements 1.2, 1.3, 1.4, 1.5
# ---------------------------------------------------------------------------

@given(match_result=valid_match_result(), config=valid_config())
@settings(max_examples=200)
def test_property_1_output_schema_invariant(match_result, config):
    """
    For any valid match_result and config, decision_controller() returns a dict
    with exactly the keys final_decision, reason, priority_score, where
    final_decision is in {APPLY, SKIP, REVIEW}, reason is non-empty, and
    priority_score is in [0.0, 1.0].
    """
    result = decision_controller(match_result, {}, config)

    # Correct keys
    assert set(result.keys()) == {"final_decision", "reason", "priority_score"}

    # final_decision is one of the three valid values
    assert result["final_decision"] in {"APPLY", "SKIP", "REVIEW"}

    # reason is a non-empty string
    assert isinstance(result["reason"], str)
    assert len(result["reason"]) > 0

    # priority_score is a float in [0.0, 1.0]
    assert isinstance(result["priority_score"], float)
    assert 0.0 <= result["priority_score"] <= 1.0


# ---------------------------------------------------------------------------
# Property 2: REJECT Tier Always Produces SKIP (Short-Circuit)
# Feature: decision-controller, Property 2: REJECT Tier Always Produces SKIP
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    role=_SUB_SCORE,
    experience=_SUB_SCORE,
    config=valid_config(),
)
@settings(max_examples=200)
def test_property_2_reject_always_skip(final_score, skill, role, experience, config):
    """
    For any match_result with decision="REJECT", regardless of sub-scores and
    config, decision_controller() returns final_decision="SKIP".
    """
    match_result = _make_match_result("REJECT", final_score, skill, role, experience)
    result = decision_controller(match_result, {}, config)
    assert result["final_decision"] == "SKIP"


# ---------------------------------------------------------------------------
# Property 3: LOW Tier Always Produces SKIP
# Feature: decision-controller, Property 3: LOW Tier Always Produces SKIP
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    role=_SUB_SCORE,
    experience=_SUB_SCORE,
    config=valid_config(),
)
@settings(max_examples=200)
def test_property_3_low_always_skip(final_score, skill, role, experience, config):
    """
    For any match_result with decision="LOW", regardless of sub-scores and
    config, decision_controller() returns final_decision="SKIP".
    """
    match_result = _make_match_result("LOW", final_score, skill, role, experience)
    result = decision_controller(match_result, {}, config)
    assert result["final_decision"] == "SKIP"


# ---------------------------------------------------------------------------
# Property 4: Skill Below Threshold Always Produces SKIP
# Feature: decision-controller, Property 4: Skill Below Threshold Always Produces SKIP
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------

@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    role=_SUB_SCORE,
    experience=_SUB_SCORE,
    threshold=_THRESHOLD,
    tier=st.sampled_from(["HIGH", "MEDIUM"]),
)
@settings(max_examples=200)
def test_property_4_skill_below_threshold_skip(
    final_score, skill, role, experience, threshold, tier
):
    """
    For any match_result with decision in {HIGH, MEDIUM} and
    breakdown["skill"] < threshold, decision_controller() returns SKIP.
    """
    assume(skill < threshold)

    match_result = _make_match_result(tier, final_score, skill, role, experience)
    config = {"skill_score_threshold": threshold}
    result = decision_controller(match_result, {}, config)
    assert result["final_decision"] == "SKIP"


# ---------------------------------------------------------------------------
# Property 5: Role Zero Always Produces SKIP
# Feature: decision-controller, Property 5: Role Zero Always Produces SKIP
# Validates: Requirements 4.1
# ---------------------------------------------------------------------------

@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    experience=_SUB_SCORE,
    threshold=_THRESHOLD,
    tier=st.sampled_from(["HIGH", "MEDIUM"]),
)
@settings(max_examples=200)
def test_property_5_role_zero_skip(final_score, skill, experience, threshold, tier):
    """
    For any match_result with decision in {HIGH, MEDIUM}, skill >= threshold,
    and role == 0.0, decision_controller() returns SKIP.
    """
    assume(skill >= threshold)

    match_result = _make_match_result(tier, final_score, skill, role=0.0, experience=experience)
    config = {"skill_score_threshold": threshold}
    result = decision_controller(match_result, {}, config)
    assert result["final_decision"] == "SKIP"


# ---------------------------------------------------------------------------
# Property 6: Experience Zero Downgrades by Exactly One Level
# Feature: decision-controller, Property 6: Experience Zero Downgrades by Exactly One Level
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------

@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    role=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
    threshold=_THRESHOLD,
    tier=st.sampled_from(["HIGH", "MEDIUM"]),
)
@settings(max_examples=200)
def test_property_6_experience_zero_downgrades_one_level(
    final_score, skill, role, threshold, tier
):
    """
    For any match_result with decision in {HIGH, MEDIUM}, skill >= threshold,
    role > 0.0, and experience == 0.0, decision_controller() returns a
    final_decision exactly one level below the Layer-1 decision:
    APPLY → REVIEW or REVIEW → SKIP.
    """
    assume(skill >= threshold)
    assume(role > 0.0)

    match_result = _make_match_result(tier, final_score, skill, role, experience=0.0)
    config = {"skill_score_threshold": threshold}
    result = decision_controller(match_result, {}, config)

    # Determine expected Layer-1 decision
    layer1_decision = "APPLY" if tier == "HIGH" else "REVIEW"

    # Expected downgrade
    expected = "REVIEW" if layer1_decision == "APPLY" else "SKIP"
    assert result["final_decision"] == expected


# ---------------------------------------------------------------------------
# Property 7: Priority Score Is Always the Final Score Passthrough
# Feature: decision-controller, Property 7: Priority Score Passthrough
# Validates: Requirements 6.1, 6.2, 6.3
# ---------------------------------------------------------------------------

@given(match_result=valid_match_result(), config=valid_config())
@settings(max_examples=200)
def test_property_7_priority_score_passthrough(match_result, config):
    """
    For any valid inputs, priority_score == match_result["final_score"].
    """
    result = decision_controller(match_result, {}, config)
    assert result["priority_score"] == match_result["final_score"]


# ---------------------------------------------------------------------------
# Property 8: Batch Function Invariants
# Feature: decision-controller, Property 8: Batch Function Invariants
# Validates: Requirements 7.2, 7.3, 7.4, 7.5
# ---------------------------------------------------------------------------

@given(
    decisions=st.lists(decision_result_dict(), min_size=0, max_size=50),
    max_n=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=200)
def test_property_8_batch_invariants(decisions, max_n):
    """
    select_top_applications() returns only APPLY entries, sorted by
    priority_score descending, with at most max_n entries.
    """
    result = select_top_applications(decisions, max_n)

    # 1. All returned entries have final_decision == "APPLY"
    for entry in result:
        assert entry["final_decision"] == "APPLY"

    # 2. Sorted by priority_score descending
    scores = [entry["priority_score"] for entry in result]
    assert scores == sorted(scores, reverse=True)

    # 3. At most max_n entries
    assert len(result) <= max_n

    # 4. If fewer APPLY than max_n, all APPLY are returned
    apply_count = sum(1 for d in decisions if d["final_decision"] == "APPLY")
    if apply_count <= max_n:
        assert len(result) == apply_count


# ---------------------------------------------------------------------------
# Property 9: Determinism
# Feature: decision-controller, Property 9: Determinism
# Validates: Requirements 8.2
# ---------------------------------------------------------------------------

@given(match_result=valid_match_result(), config=valid_config())
@settings(max_examples=200)
def test_property_9_determinism(match_result, config):
    """
    Calling decision_controller() twice with the same arguments returns
    identical results.
    """
    result1 = decision_controller(match_result, {}, config)
    result2 = decision_controller(match_result, {}, config)
    assert result1 == result2


# ---------------------------------------------------------------------------
# Property 10: Input Immutability
# Feature: decision-controller, Property 10: Input Immutability
# Validates: Requirements 1.7
# ---------------------------------------------------------------------------

@given(match_result=valid_match_result(), config=valid_config())
@settings(max_examples=200)
def test_property_10_input_immutability(match_result, config):
    """
    decision_controller() does not modify the match_result or job_data dicts.
    """
    job_data = {"role": "Data Scientist", "skills": ["Python"], "experience_level": "senior", "tools": [], "keywords": []}

    match_result_copy = copy.deepcopy(match_result)
    job_data_copy = copy.deepcopy(job_data)
    config_copy = copy.deepcopy(config)

    decision_controller(match_result, job_data, config)

    assert match_result == match_result_copy
    assert job_data == job_data_copy
    assert config == config_copy


# ---------------------------------------------------------------------------
# Property 11: Invalid Threshold Raises ValueError
# Feature: decision-controller, Property 11: Invalid Threshold Raises ValueError
# Validates: Requirements 9.3
# ---------------------------------------------------------------------------

@given(
    match_result=valid_match_result(),
    bad_threshold=st.one_of(
        # Float outside [0.0, 1.0]
        st.floats(max_value=-0.0001, allow_nan=False, allow_infinity=False),
        st.floats(min_value=1.0001, allow_nan=False, allow_infinity=False),
        # Non-float types
        st.integers(),
        st.text(min_size=1, max_size=20),
        st.none(),
        st.booleans(),
    ),
)
@settings(max_examples=200)
def test_property_11_invalid_threshold_raises_value_error(match_result, bad_threshold):
    """
    Any config["skill_score_threshold"] that is not a float in [0.0, 1.0]
    causes decision_controller() to raise ValueError.
    """
    # Exclude booleans that are also ints in Python (True=1, False=0 are valid floats)
    # but booleans are not floats (isinstance(True, float) is False)
    config = {"skill_score_threshold": bad_threshold}
    with pytest.raises(ValueError):
        decision_controller(match_result, {}, config)


# ---------------------------------------------------------------------------
# Property 12: Reason Mentions Triggering Layer's Numeric Value
# Feature: decision-controller, Property 12: Reason Mentions Numeric Value
# Validates: Requirements 10.4
# ---------------------------------------------------------------------------

@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    role=_SUB_SCORE,
    experience=_SUB_SCORE,
    threshold=_THRESHOLD,
    tier=st.sampled_from(["HIGH", "MEDIUM"]),
)
@settings(max_examples=200)
def test_property_12_reason_mentions_numeric_values(
    final_score, skill, role, experience, threshold, tier
):
    """
    When Layer 2 triggers a SKIP, the reason contains the numeric skill score
    and threshold. When Layer 4 triggers a downgrade, the reason mentions
    experience_score.
    """
    assume(skill < threshold)  # Ensure Layer 2 triggers

    match_result = _make_match_result(tier, final_score, skill, role, experience)
    config = {"skill_score_threshold": threshold}
    result = decision_controller(match_result, {}, config)

    assert result["final_decision"] == "SKIP"
    # Reason must contain the formatted skill score and threshold
    assert f"{skill:.4f}" in result["reason"]
    assert f"{threshold:.4f}" in result["reason"]


@given(
    final_score=_FINAL_SCORE,
    skill=_SUB_SCORE,
    role=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
    threshold=_THRESHOLD,
    tier=st.sampled_from(["HIGH", "MEDIUM"]),
)
@settings(max_examples=200)
def test_property_12b_reason_mentions_experience_on_downgrade(
    final_score, skill, role, threshold, tier
):
    """
    When Layer 4 triggers a downgrade (experience == 0.0), the reason mentions
    experience_score=0.0.
    """
    assume(skill >= threshold)
    assume(role > 0.0)

    match_result = _make_match_result(tier, final_score, skill, role, experience=0.0)
    config = {"skill_score_threshold": threshold}
    result = decision_controller(match_result, {}, config)

    # Layer 4 must have triggered
    assert "experience_score=0.0" in result["reason"]
