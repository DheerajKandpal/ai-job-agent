"""
Example-based (unit) tests for scorer_v2.py.

Covers:
  - Strong match → HIGH
  - Partial match → MEDIUM or LOW
  - Unrelated job → REJECT
  - Edge cases: empty inputs, unknown role/experience, keyword cap
  - V1 scorer non-regression smoke test

Run with:
    pytest tests/test_scorer_v2_examples.py -v
"""

from __future__ import annotations

import pytest

from app.services.matcher.scorer_v2 import (
    match_resume_to_job_v2,
    _skill_score_v2,
    _tool_score_v2,
    _role_score_v2,
    _experience_score_v2,
    _keyword_score_v2,
)
from app.services.matcher.matcher import match_resume_to_job


# ---------------------------------------------------------------------------
# 6.1 Strong match → HIGH
# ---------------------------------------------------------------------------

class TestStrongMatch:
    """Resume and JD share role, skills, experience level, tools, and keywords."""

    RESUME = (
        "Senior Data Scientist with Python, SQL, machine learning, TensorFlow, "
        "PyTorch, NLP, scikit-learn. AWS, Docker, PostgreSQL. "
        "Model training, feature engineering, data analysis. 5+ years experience."
    )

    JD = (
        "Senior Data Scientist — Python, machine learning, TensorFlow, SQL, "
        "PyTorch, NLP. 5+ years. AWS, Docker, PostgreSQL. "
        "Model training, feature engineering, data analysis."
    )

    def test_strong_match_decision_is_high(self) -> None:
        result = match_resume_to_job_v2(self.RESUME, self.JD)
        assert result["decision"] == "HIGH", (
            f"Expected HIGH, got {result['decision']} (score={result['final_score']})"
        )

    def test_strong_match_score_at_least_0_70(self) -> None:
        result = match_resume_to_job_v2(self.RESUME, self.JD)
        assert result["final_score"] >= 0.70, (
            f"Expected final_score >= 0.70, got {result['final_score']}"
        )

    def test_strong_match_breakdown_keys_present(self) -> None:
        result = match_resume_to_job_v2(self.RESUME, self.JD)
        assert set(result["breakdown"].keys()) == {
            "skill", "role", "experience", "tools", "keywords"
        }


# ---------------------------------------------------------------------------
# 6.2 Partial match → MEDIUM or LOW
# ---------------------------------------------------------------------------

class TestPartialMatch:
    """Some overlapping skills but mismatched role or experience level."""

    # Mid-level Data Scientist vs Senior JD — skill overlap but experience gap
    RESUME_MID_DS = (
        "Mid-level Data Scientist with Python, SQL, scikit-learn, "
        "machine learning, NLP. AWS, PostgreSQL. Data analysis, model training."
    )

    JD_SENIOR_DS = (
        "Senior Data Scientist — Python, machine learning, TensorFlow, SQL, "
        "PyTorch, NLP. 5+ years. AWS, Docker, PostgreSQL. "
        "Model training, feature engineering, data analysis."
    )

    # Backend engineer applying for a data scientist role — role mismatch
    RESUME_BACKEND = (
        "Backend Engineer with Python, SQL, FastAPI, REST. "
        "PostgreSQL, Docker, AWS. API development, automation. 3+ years."
    )

    def test_partial_match_score_in_range(self) -> None:
        result = match_resume_to_job_v2(self.RESUME_MID_DS, self.JD_SENIOR_DS)
        score = result["final_score"]
        assert 0.25 <= score < 0.70, (
            f"Expected 0.25 <= score < 0.70, got {score}"
        )

    def test_partial_match_decision_is_medium_or_low(self) -> None:
        result = match_resume_to_job_v2(self.RESUME_MID_DS, self.JD_SENIOR_DS)
        assert result["decision"] in ("MEDIUM", "LOW"), (
            f"Expected MEDIUM or LOW, got {result['decision']}"
        )

    def test_role_mismatch_reduces_score(self) -> None:
        result = match_resume_to_job_v2(self.RESUME_BACKEND, self.JD_SENIOR_DS)
        # Backend engineer vs Data Scientist — different role groups → role score 0.0
        assert result["breakdown"]["role"] == 0.0, (
            f"Expected role score 0.0 for cross-group mismatch, "
            f"got {result['breakdown']['role']}"
        )


# ---------------------------------------------------------------------------
# 6.3 Unrelated job → REJECT
# ---------------------------------------------------------------------------

class TestUnrelatedJob:
    """No overlapping skills, tools, or keywords with JD."""

    RESUME = (
        "Data Analyst with Python, SQL, Power BI, Tableau. "
        "Data analysis, reporting, dashboards."
    )

    JD_PLUMBER = (
        "Experienced plumber required. 10+ years of pipe fitting, "
        "drainage systems, and boiler installation. No IT skills needed."
    )

    def test_unrelated_job_decision_is_reject(self) -> None:
        result = match_resume_to_job_v2(self.RESUME, self.JD_PLUMBER)
        assert result["decision"] == "REJECT", (
            f"Expected REJECT, got {result['decision']} (score={result['final_score']})"
        )

    def test_unrelated_job_score_below_0_25(self) -> None:
        result = match_resume_to_job_v2(self.RESUME, self.JD_PLUMBER)
        assert result["final_score"] < 0.25, (
            f"Expected final_score < 0.25, got {result['final_score']}"
        )


# ---------------------------------------------------------------------------
# 6.4 Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    # --- Empty / None job description ---

    def test_empty_job_description_returns_reject(self) -> None:
        result = match_resume_to_job_v2("Python developer", "")
        assert result["decision"] == "REJECT"
        assert result["final_score"] == 0.0

    def test_empty_job_description_all_breakdown_zeros(self) -> None:
        result = match_resume_to_job_v2("Python developer", "")
        for key, value in result["breakdown"].items():
            assert value == 0.0, f"breakdown[{key!r}] should be 0.0, got {value}"

    def test_none_job_description_returns_reject(self) -> None:
        # None is coerced to empty string by the guard
        result = match_resume_to_job_v2("Python developer", None)  # type: ignore[arg-type]
        assert result["decision"] == "REJECT"
        assert result["final_score"] == 0.0

    def test_empty_resume_text(self) -> None:
        result = match_resume_to_job_v2("", "Senior Data Scientist Python SQL 5+ years")
        # All candidate fields are empty → skill/tool/keyword scores are 0.0
        assert result["breakdown"]["skill"] == 0.0
        assert result["breakdown"]["tools"] == 0.0
        assert result["breakdown"]["keywords"] == 0.0

    # --- Unknown role on job side ---

    def test_unknown_job_role_gives_role_score_0_5(self) -> None:
        """
        When the JD has no recognisable role, parse_job_description returns
        role='Unknown', which should yield role_score=0.5.
        """
        score = _role_score_v2("Unknown", "Data Scientist")
        assert score == 0.5, f"Expected 0.5 for Unknown job role, got {score}"

    def test_unknown_job_role_in_full_pipeline(self) -> None:
        # A JD with no role keywords — role will be "Unknown"
        jd_no_role = "We need someone with Python and SQL. 3+ years experience."
        resume = "Data Analyst with Python, SQL. Data analysis."
        result = match_resume_to_job_v2(resume, jd_no_role)
        # Role score should be 0.5 (neutral) since job role is Unknown
        assert result["breakdown"]["role"] == 0.5, (
            f"Expected role score 0.5 for Unknown job role, "
            f"got {result['breakdown']['role']}"
        )

    # --- Unknown experience on either side ---

    def test_unknown_experience_level_gives_0_5(self) -> None:
        assert _experience_score_v2("unknown", "senior") == 0.5
        assert _experience_score_v2("senior", "unknown") == 0.5
        assert _experience_score_v2("unknown", "unknown") == 0.5

    def test_unknown_experience_in_full_pipeline(self) -> None:
        # JD with no seniority signals → experience_level='unknown'
        jd_no_level = "Data Scientist needed. Python, SQL, machine learning required."
        resume_no_level = "Data Scientist with Python, SQL, machine learning."
        result = match_resume_to_job_v2(resume_no_level, jd_no_level)
        assert result["breakdown"]["experience"] == 0.5, (
            f"Expected experience score 0.5 when both levels are unknown, "
            f"got {result['breakdown']['experience']}"
        )

    # --- Keyword cap ---

    def test_keyword_cap_at_0_5(self) -> None:
        """Even a perfect keyword match is capped at 0.5."""
        keywords = ["Data Analysis", "Reporting", "Dashboard", "Automation", "ETL"]
        score = _keyword_score_v2(keywords, keywords)
        assert score == 0.5, f"Expected keyword score capped at 0.5, got {score}"

    def test_keyword_stuffing_capped_in_full_pipeline(self) -> None:
        """
        A resume that matches all job keywords should still have keyword
        sub-score <= 0.5.
        """
        jd = (
            "Data Analyst. Python, SQL. Data analysis, reporting, dashboards, "
            "automation, ETL, data cleaning, data transformation, data modeling, "
            "data visualization, A/B testing, statistical analysis."
        )
        # Resume repeats all the same keywords
        resume = (
            "Data Analyst with Python, SQL. Data analysis, reporting, dashboards, "
            "automation, ETL, data cleaning, data transformation, data modeling, "
            "data visualization, A/B testing, statistical analysis."
        )
        result = match_resume_to_job_v2(resume, jd)
        assert result["breakdown"]["keywords"] <= 0.5, (
            f"Keyword score should be capped at 0.5, got {result['breakdown']['keywords']}"
        )

    # --- Sub-score boundary values ---

    def test_skill_score_zero_when_no_required_skills(self) -> None:
        assert _skill_score_v2([], ["Python", "SQL"]) == 0.0

    def test_tool_score_zero_when_no_required_tools(self) -> None:
        assert _tool_score_v2([], ["Docker", "AWS"]) == 0.0

    def test_keyword_score_zero_when_no_required_keywords(self) -> None:
        assert _keyword_score_v2([], ["Data Analysis"]) == 0.0

    def test_skill_score_full_match(self) -> None:
        skills = ["Python", "SQL", "Machine Learning"]
        assert _skill_score_v2(skills, skills) == 1.0

    def test_skill_score_no_match(self) -> None:
        assert _skill_score_v2(["Python", "SQL"], ["Java", "Rust"]) == 0.0

    def test_experience_overqualified_scores_1_0(self) -> None:
        """Senior candidate vs junior requirement → 1.0 (overqualified, not penalised)."""
        assert _experience_score_v2("junior", "senior") == 1.0

    def test_experience_two_levels_below_scores_0_0(self) -> None:
        """Junior candidate vs senior requirement → 0.0."""
        assert _experience_score_v2("senior", "junior") == 0.0

    def test_role_exact_match(self) -> None:
        assert _role_score_v2("data scientist", "data scientist") == 1.0

    def test_role_same_group(self) -> None:
        # data scientist and data analyst are both in DATA_ROLES
        assert _role_score_v2("data scientist", "data analyst") == 0.6

    def test_role_cross_group(self) -> None:
        # data scientist (DATA_ROLES) vs software engineer (ENGINEERING_ROLES)
        assert _role_score_v2("data scientist", "software engineer") == 0.0

    # --- Output structure ---

    def test_output_has_correct_keys(self) -> None:
        result = match_resume_to_job_v2("Python developer", "Python developer needed")
        assert set(result.keys()) == {"final_score", "breakdown", "decision"}
        assert set(result["breakdown"].keys()) == {
            "skill", "role", "experience", "tools", "keywords"
        }

    def test_final_score_rounded_to_4dp(self) -> None:
        result = match_resume_to_job_v2(
            "Mid Data Scientist Python SQL machine learning",
            "Senior Data Scientist Python SQL TensorFlow PyTorch NLP 5+ years"
        )
        score = result["final_score"]
        assert score == round(score, 4), f"Score {score} not rounded to 4 dp"

    def test_decision_is_valid_literal(self) -> None:
        for jd in [
            "Senior Data Scientist Python SQL 5+ years",
            "Junior Data Analyst SQL Excel",
            "Plumber 10 years pipe fitting",
            "",
        ]:
            result = match_resume_to_job_v2("Python SQL Data Analyst", jd)
            assert result["decision"] in ("HIGH", "MEDIUM", "LOW", "REJECT")


# ---------------------------------------------------------------------------
# 6.5 V1 scorer non-regression
# ---------------------------------------------------------------------------

class TestV1NonRegression:
    """Verify that the v1 scorer is still callable and returns expected keys."""

    def test_v1_returns_expected_keys(self) -> None:
        resume = {
            "skills": ["Python", "SQL"],
            "summary": "Data analyst with 2 years experience.",
        }
        jd = "Looking for a Data Analyst with Python and SQL skills."
        result = match_resume_to_job(resume, jd)
        assert "match_score" in result, "v1 missing 'match_score'"
        assert "matched_skills" in result, "v1 missing 'matched_skills'"
        assert "missing_skills" in result, "v1 missing 'missing_skills'"

    def test_v1_score_is_float_in_range(self) -> None:
        resume = {"skills": ["Python", "SQL"], "summary": "analyst"}
        jd = "Python SQL developer needed."
        result = match_resume_to_job(resume, jd)
        assert isinstance(result["match_score"], float)
        assert 0.0 <= result["match_score"] <= 1.0

    def test_v1_matched_skills_is_list(self) -> None:
        resume = {"skills": ["Python", "SQL"], "summary": "analyst"}
        jd = "Python SQL developer needed."
        result = match_resume_to_job(resume, jd)
        assert isinstance(result["matched_skills"], list)
        assert isinstance(result["missing_skills"], list)

    def test_v1_and_v2_coexist(self) -> None:
        """Both scorers can be called in the same process without interference."""
        resume_dict = {"skills": ["Python", "SQL"], "summary": "Data analyst"}
        resume_text = "Data Analyst with Python and SQL. Data analysis."
        jd = "Data Analyst with Python and SQL skills required."

        v1_result = match_resume_to_job(resume_dict, jd)
        v2_result = match_resume_to_job_v2(resume_text, jd)

        assert "match_score" in v1_result
        assert "final_score" in v2_result
