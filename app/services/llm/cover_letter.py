"""
cover_letter.py
---------------
LLM-based cover letter generation via Ollama.

Reliability guarantee
---------------------
generate_cover_letter() NEVER raises.  If the LLM is unavailable, times out,
or returns empty output, it returns a short professional template so the API
always returns HTTP 200 with a usable cover letter.
"""

import json
import os

from app.core.logging import get_logger
from app.services.llm.ollama_client import _ollama_env, _run_ollama  # noqa: F401 (env kept for symmetry)

logger = get_logger(__name__)

# Returned whenever the LLM cannot be reached or returns nothing.
_FALLBACK_COVER_LETTER = (
    "Dear Hiring Manager, "
    "I am interested in this role and believe my skills match. "
    "Regards."
)


def generate_cover_letter(job_description: str, resume_json: dict) -> str:
    """
    Generate a tailored cover letter for *job_description* using *resume_json*.

    Reliability guarantee
    ---------------------
    This function NEVER raises.  On any LLM failure it returns
    ``_FALLBACK_COVER_LETTER`` so the API always returns HTTP 200.

    Parameters
    ----------
    job_description : str
        The job posting text.
    resume_json : dict
        The candidate's resume as a Python dict (from the resumes table).

    Returns
    -------
    str  Cover letter text, or the fallback template on failure.
    """
    resume_text = json.dumps(resume_json, ensure_ascii=True, indent=2)

    system_prompt = (
        "You are a professional cover letter writer.\n\n"
        "STRICT RULES:\n"
        "- Do NOT add fake experience or skills\n"
        "- Use ONLY information from resume\n"
        "- Align with job description\n"
        "- Keep it concise and impactful"
    )

    user_prompt = (
        f"Resume JSON:\n{resume_text}\n\n"
        f"Job Description:\n{job_description}\n\n"
        "TASK:\n"
        "- Write a tailored cover letter\n"
        "- Focus on relevant skills and experience\n"
        "- Keep tone professional"
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    try:
        output = _run_ollama(full_prompt, "cover_letter")
    except Exception as exc:
        logger.error(
            "llm unavailable: cover_letter returning fallback (%s)", exc,
            extra={"llm_call": "cover_letter", "outcome": "fallback"},
        )
        return _FALLBACK_COVER_LETTER

    if not output:
        logger.error(
            "llm empty output: cover_letter returning fallback",
            extra={"llm_call": "cover_letter", "outcome": "fallback"},
        )
        return _FALLBACK_COVER_LETTER

    return output
