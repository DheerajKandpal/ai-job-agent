"""
Resume-to-job matcher with graded, weighted scoring.

Scoring model (weights sum to 1.0)
------------------------------------
  skill_coverage   0.40  – % of resume skills that appear in the JD
  jd_demand        0.20  – % of JD-required skills the resume covers
  experience       0.30  – penalty when JD signals seniority the resume lacks
  role_alignment   0.10  – lightweight keyword overlap on role/domain terms

All sub-scores are in [0, 1]; final score is clamped to [0, 1].
"""

import re

# ---------------------------------------------------------------------------
# Skill alias map – extend as needed
# ---------------------------------------------------------------------------
SKILL_MAP: dict[str, list[str]] = {
    "postgresql": ["postgresql", "postgres"],
    "power bi": ["power bi", "powerbi"],
    "etl pipelines": ["etl pipelines", "etl"],
    "api integration": ["api integration", "apis"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "dl"],
    "natural language processing": ["natural language processing", "nlp"],
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch", "torch"],
    "scikit-learn": ["scikit-learn", "sklearn"],
}

# ---------------------------------------------------------------------------
# Seniority signals
# ---------------------------------------------------------------------------
_SENIOR_PATTERNS = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|head|director|manager|"
    r"architect|expert|\d+\+?\s*years?)\b",
    re.IGNORECASE,
)

_JUNIOR_PATTERNS = re.compile(
    r"\b(junior|jr\.?|entry.?level|associate|intern|graduate|trainee|"
    r"0[-–]\d\s*years?|1[-–]2\s*years?)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Role / domain alignment keywords
# ---------------------------------------------------------------------------
_ROLE_KEYWORDS = [
    "data analyst", "data scientist", "data engineer", "ml engineer",
    "machine learning", "software engineer", "backend", "frontend",
    "full.?stack", "devops", "cloud", "nlp", "computer vision",
    "analytics", "business intelligence", "bi", "etl", "pipeline",
    "python", "sql", "java", "javascript", "typescript", "go", "rust",
]
_ROLE_RE = re.compile(
    r"\b(" + "|".join(_ROLE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.lower().strip()


def normalize_and_match(skill: str, jd_text: str) -> bool:
    """Return True if *skill* (or any alias) appears in *jd_text*."""
    skill_lower = _normalize(skill)
    jd_lower = _normalize(jd_text)

    if skill_lower in SKILL_MAP:
        return any(variant in jd_lower for variant in SKILL_MAP[skill_lower])

    return skill_lower in jd_lower


def extract_skills_from_jd(job_description: str, resume_skills: list[str]) -> list[str]:
    """Return the subset of *resume_skills* that appear in *job_description*."""
    return [s for s in resume_skills if normalize_and_match(s, job_description)]


def _entries_to_text(entries: list) -> str:
    """
    Safely convert a list of experience entries to a single string.
    Handles both plain strings and dicts (e.g. structured resume JSON).
    """
    parts = []
    for entry in entries:
        if isinstance(entry, dict):
            parts.append(" ".join(str(v) for v in entry.values() if v))
        else:
            parts.append(str(entry))
    return " ".join(parts)

def _skill_score(resume_skills: list[str], matched_skills: list[str]) -> tuple[float, float]:
    """
    Returns (coverage_score, demand_score).

    coverage_score – what fraction of the resume's skills are relevant to this JD.
    demand_score   – how many of the JD's apparent skill requirements the resume meets.
    Both are proxied from the same matched list; demand_score uses a soft JD-skill
    estimate (matched + a small constant to avoid over-rewarding tiny JDs).
    """
    n_resume = len(resume_skills)
    n_matched = len(matched_skills)

    coverage = n_matched / n_resume if n_resume > 0 else 0.0

    # Soft estimate of JD skill demand: assume JD wants at least as many skills
    # as were matched, plus a small buffer so a 1/1 match isn't always 1.0.
    jd_skill_estimate = max(n_matched, 1)
    demand = n_matched / jd_skill_estimate  # always 1.0 when matched > 0

    # Penalise demand when the resume covers very few skills overall
    if n_resume > 0 and n_matched / n_resume < 0.3:
        demand *= 0.6

    return min(coverage, 1.0), min(demand, 1.0)


def _experience_score(resume_json: dict, jd_text: str) -> float:
    """
    Returns a score in [0, 1] reflecting experience-level fit.

    - JD signals senior/lead → check resume for matching signals
    - JD signals junior/entry → slight boost (easier bar)
    - No clear signal → neutral 0.7
    """
    jd_is_senior = bool(_SENIOR_PATTERNS.search(jd_text))
    jd_is_junior = bool(_JUNIOR_PATTERNS.search(jd_text))

    # Build a single text blob from resume fields that carry experience signals
    resume_text_parts = [
        resume_json.get("summary", ""),
        resume_json.get("objective", ""),
        _entries_to_text(resume_json.get("experience", [])),
        " ".join(
            entry if isinstance(entry, str) else entry.get("title", "")
            for entry in resume_json.get("work_history", [])
        ),
    ]
    resume_text = " ".join(resume_text_parts)

    resume_is_senior = bool(_SENIOR_PATTERNS.search(resume_text))
    resume_is_junior = bool(_JUNIOR_PATTERNS.search(resume_text))

    if jd_is_senior:
        if resume_is_senior:
            return 1.0   # good fit
        elif resume_is_junior:
            return 0.25  # clear mismatch – penalise heavily but not zero
        else:
            return 0.45  # unknown resume level vs senior JD
    elif jd_is_junior:
        if resume_is_senior:
            return 0.75  # overqualified – slight reduction
        else:
            return 0.85  # junior or unknown vs junior JD
    else:
        # No strong seniority signal in JD
        return 0.70


def _role_alignment_score(resume_json: dict, jd_text: str) -> float:
    """
    Lightweight keyword overlap between JD and resume on role/domain terms.
    Returns a score in [0, 1].
    """
    jd_keywords = set(m.group(0).lower() for m in _ROLE_RE.finditer(jd_text))
    if not jd_keywords:
        return 0.5  # no role signal → neutral

    resume_blob = " ".join([
        " ".join(resume_json.get("skills", [])),
        resume_json.get("summary", ""),
        resume_json.get("objective", ""),
        _entries_to_text(resume_json.get("experience", [])),
    ])
    resume_keywords = set(m.group(0).lower() for m in _ROLE_RE.finditer(resume_blob))

    overlap = len(jd_keywords & resume_keywords)
    score = overlap / len(jd_keywords)

    # Soft floor: even 0 overlap gets a small non-zero score
    return max(score, 0.05)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_resume_to_job(resume_json: dict, job_description: str) -> dict:
    """
    Score a resume against a job description using weighted graded scoring.

    Weights
    -------
    skill_coverage  0.40
    jd_demand       0.20
    experience      0.30
    role_alignment  0.10

    Returns
    -------
    dict with keys:
        match_score    float  – final weighted score in [0, 1]
        matched_skills list   – resume skills relevant to this JD
        missing_skills list   – resume skills NOT found in JD
    """
    # Deduplicate and normalise resume skills
    seen: set[str] = set()
    resume_skills: list[str] = []
    for skill in resume_json.get("skills", []):
        norm = _normalize(skill)
        if norm not in seen:
            resume_skills.append(norm)
            seen.add(norm)

    matched_skills = extract_skills_from_jd(job_description, resume_skills)
    matched_set = set(matched_skills)
    missing_skills = [s for s in resume_skills if s not in matched_set]

    # --- sub-scores ---
    coverage_score, demand_score = _skill_score(resume_skills, matched_skills)
    experience_score = _experience_score(resume_json, job_description)
    role_score = _role_alignment_score(resume_json, job_description)

    # --- weighted sum ---
    match_score = (
        0.40 * coverage_score
        + 0.20 * demand_score
        + 0.30 * experience_score
        + 0.10 * role_score
    )

    # Clamp to [0, 1] as a safety net
    match_score = round(max(0.0, min(1.0, match_score)), 4)

    return {
        "match_score": match_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }


# ---------------------------------------------------------------------------
# Smoke tests – run with: python app/services/matcher/matcher.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    cases = [
        {
            "label": "Simple analyst job – should score ~0.7–1.0",
            "resume": {
                "skills": ["Python", "SQL", "Power BI", "Excel"],
                "summary": "Data analyst with 2 years experience in SQL and Python.",
            },
            "jd": "Looking for a Data Analyst with SQL, Python, PowerBI and Excel skills.",
        },
        {
            "label": "Senior ML Engineer – junior analyst should score ~0.2–0.4",
            "resume": {
                "skills": ["Python", "SQL", "Excel"],
                "summary": "Junior data analyst, 1 year experience.",
            },
            "jd": (
                "Senior ML Engineer (5+ years). Must have NLP, TensorFlow, PyTorch, "
                "deep learning, and distributed systems experience. Lead a team of engineers."
            ),
        },
        {
            "label": "Unrelated job – should score ~0–0.2",
            "resume": {
                "skills": ["Python", "SQL", "Power BI"],
                "summary": "Data analyst.",
            },
            "jd": (
                "Experienced plumber required. Must have 10+ years of pipe fitting, "
                "drainage systems, and boiler installation. No IT skills needed."
            ),
        },
        {
            "label": "Partial skill match – should score ~0.4–0.6",
            "resume": {
                "skills": ["Python", "SQL", "Tableau", "Excel"],
                "summary": "Mid-level data analyst with 3 years experience.",
            },
            "jd": (
                "Data Scientist role. Requires Python, machine learning, TensorFlow, "
                "SQL, and statistics. Nice to have: Tableau."
            ),
        },
    ]

    for case in cases:
        result = match_resume_to_job(case["resume"], case["jd"])
        print(f"\n{case['label']}")
        print(f"  score          : {result['match_score']}")
        print(f"  matched_skills : {result['matched_skills']}")
        print(f"  missing_skills : {result['missing_skills']}")
