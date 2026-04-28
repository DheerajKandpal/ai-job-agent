"""
test_pipeline.py
----------------
Integration smoke test: fetches a resume from PostgreSQL and runs it
through the job-matching logic.

Usage:
    python app/test_pipeline.py
"""

import sys
import json

from app.services.tracker.db_service import get_resume_by_version
from app.services.matcher.matcher import match_resume_to_job
from app.services.llm.ollama_client import generate_tailored_resume
from app.services.validation.threshold import passes_threshold
from app.services.llm.cover_letter import generate_cover_letter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RESUME_VERSION = "base_v2"

JOB_DESCRIPTION = """
Looking for a Data Analyst with SQL, Python, Power BI and ETL pipeline experience.
Experience with APIs and data processing is a plus.
"""


def score_text_against_jd(text: str, job_description: str, skills: list) -> float:
    text_lower = text.lower()
    jd_lower = job_description.lower()

    normalized_skills = []
    seen = set()
    for skill in skills:
        if not isinstance(skill, str):
            continue
        skill_lower = skill.lower()
        if skill_lower not in seen:
            normalized_skills.append(skill_lower)
            seen.add(skill_lower)

    jd_skills = [skill for skill in normalized_skills if skill in jd_lower]
    if len(jd_skills) == 0:
        return 0.0

    matched = sum(1 for skill in jd_skills if skill in text_lower)
    return matched / len(jd_skills)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
print(f"[pipeline] Fetching resume '{RESUME_VERSION}' from database ...")
resume = get_resume_by_version(RESUME_VERSION)

if resume is None:
    print(f"[pipeline] ERROR: Resume '{RESUME_VERSION}' not found or DB unavailable. Exiting.")
    sys.exit(1)

print(f"[pipeline] Resume loaded. Running matcher ...\n")

result = match_resume_to_job(resume, JOB_DESCRIPTION)

if not passes_threshold(result["match_score"]):
    print("[PIPELINE] Rejected: below threshold")
    sys.exit(0)

tailored_resume = generate_tailored_resume(resume, JOB_DESCRIPTION)
tailored_result = match_resume_to_job(tailored_resume, JOB_DESCRIPTION)

if not passes_threshold(tailored_result["match_score"]):
    print("[PIPELINE] Tailored resume rejected: below 5% match threshold")
    print("[PIPELINE] Falling back to original resume")
    final_resume = resume
else:
    print("[PIPELINE] Tailored resume accepted")
    final_resume = tailored_resume

cover_letter = generate_cover_letter(final_resume, JOB_DESCRIPTION)
cover_score = score_text_against_jd(
    cover_letter,
    JOB_DESCRIPTION,
    final_resume.get("skills", []),
)

if not passes_threshold(cover_score):
    print("[PIPELINE] Cover letter rejected (low alignment)")
    cover_letter = ""
else:
    print("[PIPELINE] Cover letter accepted")

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
print("\n--- MATCH RESULT ---")
print(f"Score: {result['match_score']}")
print(f"Matched: {result['matched_skills']}")
print(f"Missing: {result['missing_skills']}")

print("\n--- TAILORED RESUME ---")
print(json.dumps(tailored_resume, indent=2))

if tailored_resume == resume:
    print("[LLM] No changes or rejected due to safety")

print("\n--- FINAL VALIDATION ---")
print(f"Original Score : {result['match_score']}")
print(f"Tailored Score : {tailored_result['match_score']}")
print(f"Cover Letter Score : {cover_score}")

print("\n--- FINAL RESUME USED ---")
print(json.dumps(final_resume, indent=2))

print("\n--- COVER LETTER ---")
print(cover_letter if cover_letter else "[EMPTY / REJECTED]")
