import json
import os
import subprocess

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _ollama_env() -> dict[str, str]:
    env = os.environ.copy()
    env["OLLAMA_HOST"] = settings.OLLAMA_BASE_URL
    return env


def generate_cover_letter(resume_json: dict, job_description: str) -> str:
    resume_text = json.dumps(resume_json, ensure_ascii=True, indent=2)

    system_prompt = """
You are a professional cover letter writer.

STRICT RULES:
- Do NOT add fake experience or skills
- Use ONLY information from resume
- Align with job description
- Keep it concise and impactful
""".strip()

    user_prompt = (
        f"Resume JSON:\n{resume_text}\n\n"
        f"Job Description:\n{job_description}\n\n"
        "TASK:\n"
        "- Write a tailored cover letter\n"
        "- Focus on relevant skills and experience\n"
        "- Keep tone professional"
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    logger.info("llm call start: cover_letter")
    try:
        result = subprocess.run(
            ["ollama", "run", settings.MODEL_NAME],
            input=full_prompt,
            text=True,
            capture_output=True,
            timeout=settings.LLM_TIMEOUT,
            env=_ollama_env(),
            check=False,
        )
    except (OSError, ValueError) as exc:
        logger.error("llm call error: cover_letter (%s)", exc)
        return ""

    if result.returncode != 0:
        logger.error("llm call error: cover_letter (code=%s)", result.returncode)
        return ""

    logger.info("llm call end: cover_letter")
    return result.stdout.strip()
