"""
scorer.py — Lightweight job quality scorer for the auto_apply pipeline.

Public interface
----------------
score_job(job: dict) -> float
    Evaluate a job dict and return a composite quality score in [0.0, 100.0].
    Pure function: no side effects, no logging, no I/O.

Module-level constants
----------------------
THRESHOLD     : float      — minimum score required to process a job (60.0)
KEYWORD_LIST  : list[str]  — description keywords used for keyword match scoring
TITLE_KEYWORDS: list[str]  — title fragments used for title relevance scoring
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

THRESHOLD: float = 60.0

KEYWORD_LIST: list[str] = ["python", "sql", "data", "analysis", "dashboard"]

TITLE_KEYWORDS: list[str] = ["data analyst", "analyst", "data"]

# ---------------------------------------------------------------------------
# Tier classifier
# ---------------------------------------------------------------------------


def classify_job(score: float) -> str:
    """
    Classify a job score into a priority tier.

    Returns:
        "high"   — score >= 80
        "medium" — score >= 60
        "low"    — score <  60
    """
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


def score_job(job: dict) -> float:
    """
    Evaluate a job dict and return a composite quality score in [0.0, 100.0].

    Scoring components
    ------------------
    keyword_match    : 0–40  pts  — description contains keywords from KEYWORD_LIST
    title_relevance  : 0–20  pts  — title contains a fragment from TITLE_KEYWORDS
    apply_method     : 0–20  pts  — apply_email or apply_endpoint is present/non-empty
    description_len  : 0–10  pts  — description character length > 200
    company_presence : 0–10  pts  — company field is present and non-empty

    All string comparisons are case-insensitive (both sides lowercased).

    Args:
        job: A dict representing a single job posting. All fields are optional;
             missing or empty fields contribute 0 points to their component.

    Returns:
        A float in [0.0, 100.0] representing the job's composite quality score.
    """
    # ---------------------------------------------------------------------- #
    # Keyword match (0–40)
    # Proportional: each matched keyword contributes 40/len(KEYWORD_LIST) pts.
    # ---------------------------------------------------------------------- #
    description: str = job.get("description") or ""
    desc_lower: str = description.lower()
    matched_keywords: int = sum(1 for kw in KEYWORD_LIST if kw in desc_lower)
    keyword_score: int = round((matched_keywords / len(KEYWORD_LIST)) * 40)

    # ---------------------------------------------------------------------- #
    # Title relevance (0–20)
    # Binary: 20 pts if title contains any fragment from TITLE_KEYWORDS.
    # ---------------------------------------------------------------------- #
    title: str = job.get("title") or ""
    title_lower: str = title.lower()
    title_score: int = 20 if any(frag in title_lower for frag in TITLE_KEYWORDS) else 0

    # ---------------------------------------------------------------------- #
    # Application method availability (0–20)
    # Binary: 20 pts if apply_email or apply_endpoint is present and non-empty.
    # ---------------------------------------------------------------------- #
    has_apply_method: bool = bool(job.get("apply_email")) or bool(job.get("apply_endpoint"))
    method_score: int = 20 if has_apply_method else 0

    # ---------------------------------------------------------------------- #
    # Description length (0–10)
    # Binary: 10 pts if description is longer than 200 characters.
    # ---------------------------------------------------------------------- #
    length_score: int = 10 if len(description) > 200 else 0

    # ---------------------------------------------------------------------- #
    # Company presence bonus (0–10)
    # Binary: 10 pts if company field is present and non-empty.
    # ---------------------------------------------------------------------- #
    company_score: int = 10 if job.get("company") else 0

    # ---------------------------------------------------------------------- #
    # Aggregate — maximum possible: 40 + 20 + 20 + 10 + 10 = 100
    # ---------------------------------------------------------------------- #
    total: int = keyword_score + title_score + method_score + length_score + company_score
    return float(total)
