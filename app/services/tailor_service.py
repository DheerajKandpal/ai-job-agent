from app.config import settings
from app.services.llm.ollama_client import generate_tailored_resume
from app.services.tracker.db_service import get_resume_by_version as get_resume


def process_tailor(job_description: str) -> dict:
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    resume = get_resume(settings.RESUME_VERSION)
    if resume is None:
        raise ValueError("resume not found")

    tailored_resume = generate_tailored_resume(job_description, resume)

    if isinstance(tailored_resume, dict):
        normalized_summary = str(tailored_resume.get("summary", ""))
        raw_experience = tailored_resume.get("experience", [])
        raw_skills = tailored_resume.get("skills", [])
    else:
        normalized_summary = ""
        raw_experience = []
        raw_skills = []

    normalized_experience = list(raw_experience) if isinstance(raw_experience, (list, tuple, set)) else []
    normalized_skills = list(raw_skills) if isinstance(raw_skills, (list, tuple, set)) else []

    return {
        "tailored_resume": {
            "summary": normalized_summary,
            "experience": normalized_experience,
            "skills": normalized_skills,
        }
    }
