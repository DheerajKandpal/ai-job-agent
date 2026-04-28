skill_map = {
    "postgresql": ["postgresql", "postgres"],
    "power bi": ["power bi", "powerbi"],
    "etl pipelines": ["etl pipelines", "etl"],
    "api integration": ["api integration", "apis"],
}


def normalize_and_match(skill: str, jd_text: str) -> bool:
    skill_lower = skill.lower()
    jd_lower = jd_text.lower()

    if skill_lower in skill_map:
        return any(variant in jd_lower for variant in skill_map[skill_lower])

    return skill_lower in jd_lower


def extract_skills_from_jd(job_description: str, resume_skills: list) -> list:
    """
    Return the subset of resume_skills that appear in the job description.
    """
    return [
        skill
        for skill in resume_skills
        if normalize_and_match(skill, job_description)
    ]


def match_resume_to_job(resume_json: dict, job_description: str) -> dict:
    """
    Score a resume against a job description.

    Scoring model
    -------------
    Returns
    -------
    dict with keys: match_score (float), matched_skills (list), missing_skills (list)
    """
    resume_skills = []
    seen_skills = set()
    for skill in resume_json.get("skills", []):
        normalized_skill = skill.lower()
        if normalized_skill not in seen_skills:
            resume_skills.append(normalized_skill)
            seen_skills.add(normalized_skill)

    jd_required_skills = extract_skills_from_jd(job_description, resume_skills)
    matched_skills = jd_required_skills

    matched_skill_set = set(matched_skills)
    missing_skills = [
        skill
        for skill in resume_skills
        if skill not in matched_skill_set
    ]

    if len(jd_required_skills) == 0:
        match_score = 0.0
    else:
        match_score = len(matched_skills) / len(jd_required_skills)

    return {
        "match_score": match_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }


# ---------------------------------------------------------------------------
# Quick smoke test - run with: python app/services/matcher/matcher.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    resume = {
        "skills": ["Python", "SQL", "Power BI", "Excel"]
    }

    job_description = """
Looking for a Data Analyst with SQL, Python, PowerBI and ETL experience.
Experience with Postgres is a plus.
"""

    print(match_resume_to_job(resume, job_description))
