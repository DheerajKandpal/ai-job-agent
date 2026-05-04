"""
scorer_v2.py
------------
Structured Match Scoring v2.

Replaces the heuristic, regex-heavy approach of matcher.py (v1) with a
deterministic, field-by-field comparison.  Both the job description and the
resume text are parsed through the existing parse_job_description() function,
producing structured fields on each side.  Five independent sub-scores are
then computed and combined with fixed weights into a final score, accompanied
by a four-tier decision label.

The v1 scorer (match_resume_to_job in matcher.py) is preserved unchanged.
This module is purely additive — no existing code is modified.

Public API
----------
    match_resume_to_job_v2(resume_text, job_description) -> ScoringResult

Weights
-------
    skill       0.40
    role        0.20
    experience  0.20
    tools       0.10
    keywords    0.10  (sub-score capped at 0.5 before weighting)

Decision thresholds
-------------------
    HIGH    >= 0.70
    MEDIUM  >= 0.45
    LOW     >= 0.25
    REJECT  <  0.25
"""

from __future__ import annotations

from typing import TypedDict

from app.services.parser.jd_parser import parse_job_description


# ---------------------------------------------------------------------------
# Role group constants
# ---------------------------------------------------------------------------

DATA_ROLES: frozenset[str] = frozenset([
    "data scientist",
    "data analyst",
    "ml engineer",
    "data engineer",
    "analytics engineer",
    "ai engineer",
    "research engineer",
])

ENGINEERING_ROLES: frozenset[str] = frozenset([
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "full stack engineer",
    "platform engineer",
    "devops engineer",
    "site reliability engineer",
    "cloud engineer",
])

BUSINESS_ROLES: frozenset[str] = frozenset([
    "business analyst",
    "business intelligence",
    "product manager",
])

ROLE_GROUPS: list[frozenset[str]] = [DATA_ROLES, ENGINEERING_ROLES, BUSINESS_ROLES]


# ---------------------------------------------------------------------------
# Experience level ordering
# ---------------------------------------------------------------------------

EXPERIENCE_ORDER: dict[str, int] = {
    "junior": 0,
    "mid":    1,
    "senior": 2,
}


# ---------------------------------------------------------------------------
# Decision thresholds (overrides design doc — per implementation instructions)
# ---------------------------------------------------------------------------

_THRESHOLD_HIGH:   float = 0.70
_THRESHOLD_MEDIUM: float = 0.45
_THRESHOLD_LOW:    float = 0.25


# ---------------------------------------------------------------------------
# Output TypedDicts
# ---------------------------------------------------------------------------

class BreakdownDict(TypedDict):
    skill:      float   # [0.0, 1.0]
    role:       float   # 0.0 | 0.6 | 1.0
    experience: float   # 0.0 | 0.5 | 1.0
    tools:      float   # [0.0, 1.0]
    keywords:   float   # [0.0, 0.5]  (capped)


class ScoringResult(TypedDict):
    final_score: float        # [0.0, 1.0], rounded to 4 dp
    breakdown:   BreakdownDict
    decision:    str          # "HIGH" | "MEDIUM" | "LOW" | "REJECT"


# ---------------------------------------------------------------------------
# Zero-result constant (returned on empty/None job description)
# ---------------------------------------------------------------------------

_ZERO_RESULT: ScoringResult = {
    "final_score": 0.0,
    "breakdown": {
        "skill":      0.0,
        "role":       0.0,
        "experience": 0.0,
        "tools":      0.0,
        "keywords":   0.0,
    },
    "decision": "REJECT",
}


# ---------------------------------------------------------------------------
# Sub-score functions (pure, no side effects)
# ---------------------------------------------------------------------------

def _skill_score_v2(job_skills: list[str], candidate_skills: list[str]) -> float:
    """
    Directional skill coverage: how many of the job's required skills does
    the candidate have?

    Formula: matched / len(job_skills)
    Matching is case-insensitive (uses casefold for full Unicode support).
    Returns 0.0 when job_skills is empty.
    """
    if not job_skills:
        return 0.0
    job_folded = {s.casefold() for s in job_skills}
    candidate_folded = {s.casefold() for s in candidate_skills}
    matched = len(job_folded & candidate_folded)
    return matched / len(job_folded)


def _tool_score_v2(job_tools: list[str], candidate_tools: list[str]) -> float:
    """
    Directional tool coverage: how many of the job's required tools does
    the candidate have?

    Identical formula to _skill_score_v2, applied to tools.
    Matching is case-insensitive (uses casefold for full Unicode support).
    Returns 0.0 when job_tools is empty.
    """
    if not job_tools:
        return 0.0
    job_folded = {t.casefold() for t in job_tools}
    candidate_folded = {t.casefold() for t in candidate_tools}
    matched = len(job_folded & candidate_folded)
    return matched / len(job_folded)


def _role_score_v2(job_role: str, candidate_role: str) -> float:
    """
    Categorical role alignment score.

    Rules (evaluated in order):
      1. job_role == "Unknown"                                    → 0.5  (neutral)
      2. casefold(candidate_role) == casefold(job_role)           → 1.0  (exact match)
      3. both roles in the same ROLE_GROUPS set                   → 0.6  (related)
      4. otherwise                                                → 0.0  (unrelated)
    """
    if job_role == "Unknown":
        return 0.5

    job_norm = job_role.casefold().strip()
    candidate_norm = candidate_role.casefold().strip()

    if job_norm == candidate_norm:
        return 1.0

    # Check if both roles belong to the same group
    for group in ROLE_GROUPS:
        if job_norm in group and candidate_norm in group:
            return 0.6

    return 0.0


def _experience_score_v2(job_level: str, candidate_level: str) -> float:
    """
    Directional experience alignment score.

    Ordered levels: junior (0) < mid (1) < senior (2)

    Rules:
      - Either level is "unknown"                    → 0.5  (neutral)
      - candidate rank >= required rank (at level or overqualified) → 1.0
      - candidate rank is exactly one below required → 0.5
      - candidate rank is two or more below required → 0.0
    """
    if job_level not in EXPERIENCE_ORDER or candidate_level not in EXPERIENCE_ORDER:
        return 0.5

    required_rank  = EXPERIENCE_ORDER[job_level]
    candidate_rank = EXPERIENCE_ORDER[candidate_level]
    delta = required_rank - candidate_rank  # positive = candidate is below required

    if delta <= 0:
        return 1.0
    elif delta == 1:
        return 0.5
    else:
        return 0.0


def _keyword_score_v2(job_keywords: list[str], candidate_keywords: list[str]) -> float:
    """
    Directional keyword overlap, capped at 0.5.

    Formula: min(matched / len(job_keywords), 0.5)
    Matching is case-insensitive (uses casefold for full Unicode support).
    Returns 0.0 when job_keywords is empty.

    The cap prevents keyword-stuffed resumes from earning more than 0.05
    (= 0.10 × 0.5) from this component.
    """
    if not job_keywords:
        return 0.0
    job_folded = {k.casefold() for k in job_keywords}
    candidate_folded = {k.casefold() for k in candidate_keywords}
    matched = len(job_folded & candidate_folded)
    raw = matched / len(job_folded)
    return min(raw, 0.5)


# ---------------------------------------------------------------------------
# Decision helper
# ---------------------------------------------------------------------------

def _derive_decision(final_score: float) -> str:
    """Map a final score in [0.0, 1.0] to a four-tier decision label."""
    if final_score >= _THRESHOLD_HIGH:
        return "HIGH"
    elif final_score >= _THRESHOLD_MEDIUM:
        return "MEDIUM"
    elif final_score >= _THRESHOLD_LOW:
        return "LOW"
    else:
        return "REJECT"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_resume_to_job_v2(
    resume_text: str,
    job_description: str,
) -> ScoringResult:
    """
    Score a resume against a job description using structured field comparison.

    Both inputs are parsed via parse_job_description() to extract structured
    fields (skills, tools, keywords, role, experience_level).  Five independent
    sub-scores are computed and combined with fixed weights.

    Parameters
    ----------
    resume_text : str
        Raw resume text (plain text or lightly formatted).
    job_description : str
        Raw job description text.

    Returns
    -------
    ScoringResult
        A TypedDict with keys:
            final_score  float  – weighted score in [0.0, 1.0], rounded to 4 dp
            breakdown    dict   – five sub-scores (skill, role, experience, tools, keywords)
            decision     str    – "HIGH" | "MEDIUM" | "LOW" | "REJECT"

    Weights
    -------
        skill       0.40
        role        0.20
        experience  0.20
        tools       0.10
        keywords    0.10  (keyword sub-score already capped at 0.5)

    Decision thresholds
    -------------------
        HIGH    >= 0.70
        MEDIUM  >= 0.45
        LOW     >= 0.25
        REJECT  <  0.25

    Notes
    -----
    - If job_description is None or empty, returns final_score=0.0, all-zero
      breakdown, and decision="REJECT" without calling the parser.
    - If resume_text is None or empty, the parser returns empty fields; all
      candidate-dependent sub-scores will be 0.0 or fall back to defaults.
    - The v1 scorer (match_resume_to_job in matcher.py) is not modified.
    """
    # Guard: empty / None job description → immediate REJECT
    if not job_description or not job_description.strip():
        return {
            "final_score": 0.0,
            "breakdown": {
                "skill":      0.0,
                "role":       0.0,
                "experience": 0.0,
                "tools":      0.0,
                "keywords":   0.0,
            },
            "decision": "REJECT",
        }

    # Parse both sides using the same parser
    job_parsed    = parse_job_description(job_description)
    resume_parsed = parse_job_description(resume_text or "")

    # Job side (what the job requires)
    required_skills   = job_parsed["skills"]
    required_tools    = job_parsed["tools"]
    required_keywords = job_parsed["keywords"]
    required_role     = job_parsed["role"]
    required_level    = job_parsed["experience_level"]

    # Resume side (what the candidate has)
    candidate_skills   = resume_parsed["skills"]
    candidate_tools    = resume_parsed["tools"]
    candidate_keywords = resume_parsed["keywords"]
    candidate_role     = resume_parsed["role"]
    candidate_level    = resume_parsed["experience_level"]

    # Compute five sub-scores
    skill_score      = _skill_score_v2(required_skills, candidate_skills)
    tool_score       = _tool_score_v2(required_tools, candidate_tools)
    role_score       = _role_score_v2(required_role, candidate_role)
    experience_score = _experience_score_v2(required_level, candidate_level)
    keyword_score    = _keyword_score_v2(required_keywords, candidate_keywords)

    # Weighted combination
    raw_score = (
        0.40 * skill_score
        + 0.20 * role_score
        + 0.20 * experience_score
        + 0.10 * tool_score
        + 0.10 * keyword_score
    )

    # Clamp and round
    final_score = round(max(0.0, min(1.0, raw_score)), 4)

    # Derive decision
    decision = _derive_decision(final_score)

    return {
        "final_score": final_score,
        "breakdown": {
            "skill":      skill_score,
            "role":       role_score,
            "experience": experience_score,
            "tools":      tool_score,
            "keywords":   keyword_score,
        },
        "decision": decision,
    }


# Alias for callers that use the design-doc name
score_resume_structured = match_resume_to_job_v2


# ---------------------------------------------------------------------------
# Smoke tests — run with: python app/services/matcher/scorer_v2.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    cases = [
        {
            "label": "Strong match — Senior Data Scientist",
            "resume": (
                "Senior Data Scientist with Python, SQL, machine learning, TensorFlow, "
                "PyTorch, NLP, scikit-learn. AWS, Docker, PostgreSQL. "
                "Model training, feature engineering, data analysis. 5+ years experience."
            ),
            "jd": (
                "Senior Data Scientist — Python, machine learning, TensorFlow, SQL, "
                "PyTorch, NLP. 5+ years. AWS, Docker, PostgreSQL. "
                "Model training, feature engineering, data analysis."
            ),
        },
        {
            "label": "Partial match — Mid Data Scientist vs Senior JD",
            "resume": (
                "Mid-level Data Scientist with Python, SQL, scikit-learn, "
                "machine learning, NLP. AWS, PostgreSQL. Data analysis, model training."
            ),
            "jd": (
                "Senior Data Scientist — Python, machine learning, TensorFlow, SQL, "
                "PyTorch, NLP. 5+ years. AWS, Docker, PostgreSQL. "
                "Model training, feature engineering, data analysis."
            ),
        },
        {
            "label": "Unrelated job — plumber",
            "resume": (
                "Data Analyst with Python, SQL, Power BI, Tableau. "
                "Data analysis, reporting, dashboards."
            ),
            "jd": (
                "Experienced plumber required. 10+ years of pipe fitting, "
                "drainage systems, and boiler installation. No IT skills needed."
            ),
        },
        {
            "label": "Edge case — empty job description",
            "resume": "Python developer",
            "jd": "",
        },
    ]

    for case in cases:
        result = match_resume_to_job_v2(case["resume"], case["jd"])
        print(f"\n{'─' * 60}")
        print(f"  {case['label']}")
        print(f"{'─' * 60}")
        print(json.dumps(result, indent=2))
