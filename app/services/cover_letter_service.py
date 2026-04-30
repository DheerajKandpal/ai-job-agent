from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.cover_letter import generate_cover_letter
from app.services.tracker.db_service import get_resume_by_version as get_resume

logger = get_logger(__name__)


def process_cover_letter(job_description: str) -> dict:
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    logger.info("db call start: get_resume")
    resume = get_resume(settings.RESUME_VERSION)
    logger.info("db call end: get_resume")
    if resume is None:
        raise ValueError("resume not found")

    cover_letter_text = generate_cover_letter(job_description, resume)
    return {"cover_letter": str(cover_letter_text)}
