from app.config import settings
from app.services.matcher.matcher import match_resume_to_job as match
from app.services.tracker.db_service import get_resume_by_version as get_resume


def process_match(job_description: str) -> dict:
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    resume = get_resume(settings.RESUME_VERSION)
    if resume is None:
        raise ValueError("resume not found")

    result = match(job_description, resume)

    return {
        "match_score": float(result.get("match_score", 0.0)),
        "matched_skills": list(result.get("matched_skills", [])),
    }
