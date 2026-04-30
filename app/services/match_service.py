from app.core.config import settings
from app.core.cache import get as cache_get
from app.core.cache import set as cache_set
from app.core.logging import get_logger
from app.services.matcher.matcher import match_resume_to_job as match
from app.services.tracker.db_service import get_resume_by_version as get_resume

logger = get_logger(__name__)


def process_match(job_description: str) -> dict:
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    resume = cache_get("resume")
    if resume is None:
        logger.info("db call start: get_resume")
        resume = get_resume(settings.RESUME_VERSION)
        logger.info("db call end: get_resume")
        if resume is not None:
            cache_set("resume", resume, ttl=300)
    if resume is None:
        raise ValueError("resume not found")

    result = match(job_description, resume)

    return {
        "match_score": float(result.get("match_score", 0.0)),
        "matched_skills": list(result.get("matched_skills", [])),
    }
