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


def _extract_json_block(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, end_index = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return text[index : index + end_index]
    return None


def _same_top_level_keys(original: dict, candidate: dict) -> bool:
    return set(original.keys()) == set(candidate.keys())


def _collect_skills(payload) -> set[str]:
    skills = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "skills" and isinstance(value, list):
                    for skill in value:
                        if isinstance(skill, str):
                            skills.add(skill.strip().lower())
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return skills


def generate_tailored_resume(
    resume_json: dict, job_description: str, debug: bool = False
) -> dict:
    resume_text = json.dumps(resume_json, ensure_ascii=True, indent=2)

    system_prompt = """
SYSTEM INSTRUCTION - STRICTLY FOLLOW. FAIL IF NOT FOLLOWED.

You are a deterministic resume tailoring engine.

Behavior rules:
- ONLY use facts, skills, tools, technologies, responsibilities, and experience present in base_resume.
- DO NOT add new skills.
- DO NOT add new tools.
- DO NOT add new companies, roles, dates, metrics, credentials, projects, or achievements.
- DO NOT hallucinate.
- DO NOT infer facts that are not explicitly present in base_resume.
- ONLY rewrite, reorder, and emphasize existing resume content.
- Extract relevant keywords from job_description and use them ONLY when they match existing content in base_resume.
- Preserve the meaning and truth of every resume detail.
- Return ONLY valid JSON.
- No explanation.
- No markdown.
- No extra text.
- Your entire response MUST start with '{' and end with '}'.
- Perform an internal validation step:
  - Check that all skills in output exist in base_resume.
  - Remove any skill not found in base_resume.
- If unsure, return empty valid JSON structure:
  {
    "summary": "",
    "experience": [],
    "skills": []
  }
- Before returning output:
  - Ensure the response is valid JSON.
  - Ensure it can be parsed by a strict JSON parser.
  - Ensure no trailing commas.
  - Ensure all keys and strings use double quotes.
  - Ensure no text exists before or after the JSON object.
  - If invalid, FIX it before returning.
""".strip()

    user_prompt = (
        "CONTEXT\n\n"
        "job_description:\n"
        f"{job_description}\n\n"
        "base_resume JSON:\n"
        f"{resume_text}\n\n"
        "TASK - STRICTLY FOLLOW. FAIL IF NOT FOLLOWED.\n"
        "- Extract relevant keywords from job_description.\n"
        "- Compare those keywords against ONLY the content already present in base_resume.\n"
        "- Tailor the resume by rewriting, reordering, and emphasizing matching existing content.\n"
        "- Do NOT introduce any keyword, skill, responsibility, tool, or claim unless it already exists in base_resume.\n\n"
        "OUTPUT FORMAT - MANDATORY. FAIL IF NOT FOLLOWED.\n"
        "Return EXACTLY this JSON shape and nothing else:\n"
        "{\n"
        '  "summary": "string",\n'
        '  "experience": ["string"],\n'
        '  "skills": ["string"]\n'
        "}\n\n"
        "FINAL HARD CONSTRAINTS:\n"
        "- Return ONLY valid JSON.\n"
        "- No explanation.\n"
        "- No markdown.\n"
        "- No extra text.\n"
        "- Your entire response MUST start with '{' and end with '}'.\n\n"
        "SELF-CHECK STEP:\n"
        "Perform an internal validation step:\n"
        "- Check that all skills in output exist in base_resume.\n"
        "- Remove any skill not found in base_resume.\n\n"
        "EMPTY FALLBACK RULE:\n"
        "If unsure, return empty valid JSON structure:\n"
        "{\n"
        '  "summary": "",\n'
        '  "experience": [],\n'
        '  "skills": []\n'
        "}\n\n"
        "JSON ENFORCEMENT GUARD:\n"
        "Before returning output:\n"
        "- Ensure the response is valid JSON.\n"
        "- Ensure it can be parsed by a strict JSON parser.\n"
        "- Ensure no trailing commas.\n"
        "- Ensure all keys and strings use double quotes.\n"
        "- Ensure no text exists before or after the JSON object.\n"
        "- If invalid, FIX it before returning."
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    if debug:
        logger.debug("final prompt prepared for tailor_resume")

    safe_fallback = {
        "summary": "",
        "experience": [],
        "skills": [],
    }

    def _sanitize_parsed_output(payload) -> dict:
        if not isinstance(payload, dict):
            return safe_fallback

        summary = payload.get("summary", "")
        if not isinstance(summary, str):
            summary = ""

        experience = payload.get("experience", [])
        if not isinstance(experience, list):
            experience = []

        skills = payload.get("skills", [])
        if not isinstance(skills, list):
            skills = []

        def sanitize_str_list(items: list) -> list[str]:
            sanitized = []
            for item in items:
                if isinstance(item, str):
                    sanitized.append(item)
                elif item is None:
                    continue
                else:
                    try:
                        sanitized.append(str(item))
                    except (TypeError, ValueError):
                        continue
            return sanitized

        return {
            "summary": summary,
            "experience": sanitize_str_list(experience),
            "skills": sanitize_str_list(skills),
        }

    def _extract_json_guard(text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        first_open = cleaned.find("{")
        last_close = cleaned.rfind("}")
        if first_open != -1 and last_close != -1 and first_open <= last_close:
            return cleaned[first_open : last_close + 1].strip()
        return cleaned

    def _finalize_output(payload) -> dict:
        final_output = _sanitize_parsed_output(payload)
        if debug:
            logger.debug("final sanitized result ready")
        return final_output

    sanitized_fallback = _finalize_output(safe_fallback)

    logger.info("llm call start: tailor_resume")
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
    except subprocess.TimeoutExpired as exc:
        logger.error("llm call error: tailor_resume timeout (%s)", exc)
        raise RuntimeError("LLM call timed out") from exc
    except (OSError, ValueError) as exc:
        logger.error("llm call error: tailor_resume (%s)", exc)
        raise RuntimeError(f"LLM service unavailable: {exc}") from exc

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if stderr:
        logger.error("llm stderr: tailor_resume")

    if result.returncode != 0 or not stdout:
        logger.error("llm call error: tailor_resume (code=%s)", result.returncode)
        raise RuntimeError(f"LLM call failed (code={result.returncode})")

    raw_output = stdout.strip()
    if debug:
        logger.debug("raw output received for tailor_resume")
    if not raw_output:
        raise RuntimeError("LLM returned empty output")

    raw_output = _extract_json_guard(raw_output)

    try:
        parsed_output = json.loads(raw_output)
        logger.info("llm call end: tailor_resume")
        return _finalize_output(parsed_output)
    except json.JSONDecodeError:
        correction_prompt = (
            "STRICTLY FIX THIS OUTPUT.\n"
            "Return ONLY valid JSON.\n"
            "No explanation.\n"
            "No markdown.\n"
            "Response MUST start with '{' and end with '}'.\n\n"
            f"{raw_output}"
        )

        try:
            retry_result = subprocess.run(
                ["ollama", "run", settings.MODEL_NAME],
                input=correction_prompt,
                text=True,
                capture_output=True,
                timeout=settings.LLM_TIMEOUT,
                env=_ollama_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("llm correction error: tailor_resume timeout (%s)", exc)
            raise RuntimeError("LLM correction call timed out") from exc
        except (OSError, ValueError) as exc:
            logger.error("llm correction error: tailor_resume (%s)", exc)
            raise RuntimeError(f"LLM correction service unavailable: {exc}") from exc

        retry_stdout = (retry_result.stdout or "").strip()
        retry_stderr = (retry_result.stderr or "").strip()

        if retry_stderr:
            logger.error("llm correction stderr: tailor_resume")

        if retry_result.returncode != 0 or not retry_stdout:
            logger.error(
                "llm correction error: tailor_resume (code=%s)", retry_result.returncode
            )
            raise RuntimeError(f"LLM correction call failed (code={retry_result.returncode})")

        retry_raw_output = retry_stdout.strip()
        if debug:
            logger.debug("retry output received for tailor_resume")
        if not retry_raw_output:
            raise RuntimeError("LLM correction returned empty output")

        retry_raw_output = _extract_json_guard(retry_raw_output)

        try:
            retry_parsed_output = json.loads(retry_raw_output)
            logger.info("llm call end: tailor_resume")
            return _finalize_output(retry_parsed_output)
        except json.JSONDecodeError:
            raise RuntimeError("LLM output could not be parsed as JSON after correction")


if __name__ == "__main__":
    resume = {
        "name": "Alex Doe",
        "summary": "Data analyst with 3 years of experience.",
        "skills": ["SQL", "Python"],
        "experience": [
            {
                "title": "Data Analyst",
                "company": "ABC Corp",
                "bullets": [
                    "Built weekly reports.",
                    "Analyzed sales trends using SQL and Python.",
                ],
            }
        ],
    }

    job_description = """
Looking for a Data Analyst with strong SQL skills and dashboard-building experience.
"""

    tailored = generate_tailored_resume(resume, job_description)
    logger.info("tailor smoke test result: %s", json.dumps(tailored, indent=2))
