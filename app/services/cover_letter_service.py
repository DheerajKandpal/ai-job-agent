from app.config import settings
from app.services.llm.cover_letter import generate_cover_letter
from app.services.tracker.db_service import get_resume_by_version as get_resume


def process_cover_letter(job_description: str) -> dict:
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    resume = get_resume(settings.RESUME_VERSION)
    if resume is None:
        raise ValueError("resume not found")

    cover_letter_text = generate_cover_letter(job_description, resume)
    return {"cover_letter": str(cover_letter_text)}
