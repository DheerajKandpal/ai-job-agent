"""
ollama_client.py
----------------
Subprocess-based Ollama client for resume tailoring.

Reliability contract
--------------------
- generate_tailored_resume() NEVER raises.  On any failure it returns the
  original resume fields with a [LLM_FAILED_FALLBACK] tag so the API always
  returns HTTP 200.
- _run_ollama() retries up to LLM_MAX_RETRIES times on timeout only, with a
  short delay between attempts.  All other errors fail immediately.
- Every call logs: start time, end time, duration, attempt number, and
  success/failure outcome.
"""

import json
import os
import subprocess
import time

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum number of retry attempts on timeout (1 initial + 2 retries = 3 total).
LLM_MAX_RETRIES = 2
# Seconds to wait between retry attempts.
LLM_RETRY_DELAY = 2

# Fallback tag appended to the summary when the LLM could not be reached.
_FALLBACK_TAG = "[LLM_FAILED_FALLBACK]"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _extract_json_guard(text: str) -> str:
    """Strip any leading/trailing non-JSON text around the first {...} block."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    first_open = cleaned.find("{")
    last_close = cleaned.rfind("}")
    if first_open != -1 and last_close != -1 and first_open <= last_close:
        return cleaned[first_open : last_close + 1].strip()
    return cleaned


def _run_ollama(prompt: str, call_label: str) -> str:
    """
    Run ``ollama run <model>`` with the given prompt and return stdout.

    Retries up to LLM_MAX_RETRIES times on timeout.  All other subprocess
    errors are raised immediately as RuntimeError.

    Parameters
    ----------
    prompt      : Full prompt string piped to stdin.
    call_label  : Short label used in log messages (e.g. "tailor_resume").

    Returns
    -------
    str  Raw stdout from the model (may be empty).

    Raises
    ------
    RuntimeError  On non-recoverable subprocess failure or exhausted retries.
    """
    attempt = 0
    last_exc: Exception | None = None

    while attempt <= LLM_MAX_RETRIES:
        attempt_label = f"attempt {attempt + 1}/{LLM_MAX_RETRIES + 1}"
        t_start = time.monotonic()

        logger.info(
            "llm call start: %s (%s)",
            call_label,
            attempt_label,
            extra={"llm_call": call_label, "attempt": attempt + 1},
        )

        try:
            result = subprocess.run(
                ["ollama", "run", settings.MODEL_NAME],
                input=prompt,
                text=True,
                capture_output=True,
                timeout=settings.LLM_TIMEOUT,
                env=_ollama_env(),
                check=False,
            )

            duration_ms = round((time.monotonic() - t_start) * 1000, 1)

            stderr = (result.stderr or "").strip()
            if stderr:
                logger.warning(
                    "llm stderr: %s (%s)",
                    call_label,
                    attempt_label,
                    extra={"llm_call": call_label, "attempt": attempt + 1},
                )

            if result.returncode != 0:
                logger.error(
                    "llm call failed: %s returncode=%s duration_ms=%s (%s)",
                    call_label,
                    result.returncode,
                    duration_ms,
                    attempt_label,
                    extra={
                        "llm_call": call_label,
                        "attempt": attempt + 1,
                        "returncode": result.returncode,
                        "duration_ms": duration_ms,
                        "outcome": "error",
                    },
                )
                raise RuntimeError(
                    f"LLM call failed (returncode={result.returncode})"
                )

            stdout = (result.stdout or "").strip()
            logger.info(
                "llm call success: %s duration_ms=%s (%s)",
                call_label,
                duration_ms,
                attempt_label,
                extra={
                    "llm_call": call_label,
                    "attempt": attempt + 1,
                    "duration_ms": duration_ms,
                    "outcome": "success",
                },
            )
            return stdout

        except subprocess.TimeoutExpired as exc:
            duration_ms = round((time.monotonic() - t_start) * 1000, 1)
            last_exc = exc
            logger.warning(
                "llm call timeout: %s duration_ms=%s (%s)",
                call_label,
                duration_ms,
                attempt_label,
                extra={
                    "llm_call": call_label,
                    "attempt": attempt + 1,
                    "duration_ms": duration_ms,
                    "outcome": "timeout",
                },
            )
            attempt += 1
            if attempt <= LLM_MAX_RETRIES:
                logger.info(
                    "llm call retry: %s sleeping %ss before attempt %s",
                    call_label,
                    LLM_RETRY_DELAY,
                    attempt + 1,
                    extra={"llm_call": call_label, "retry_delay": LLM_RETRY_DELAY},
                )
                time.sleep(LLM_RETRY_DELAY)
            continue

        except (OSError, ValueError) as exc:
            duration_ms = round((time.monotonic() - t_start) * 1000, 1)
            logger.error(
                "llm call error: %s %s duration_ms=%s (%s)",
                call_label,
                exc,
                duration_ms,
                attempt_label,
                extra={
                    "llm_call": call_label,
                    "attempt": attempt + 1,
                    "duration_ms": duration_ms,
                    "outcome": "error",
                },
            )
            raise RuntimeError(f"LLM service unavailable: {exc}") from exc

        except Exception as exc:
            # Final safety net — catch anything unexpected so callers can
            # decide whether to fall back rather than crash.
            duration_ms = round((time.monotonic() - t_start) * 1000, 1)
            logger.error(
                "llm call unexpected error: %s %s duration_ms=%s (%s)",
                call_label,
                exc,
                duration_ms,
                attempt_label,
                extra={
                    "llm_call": call_label,
                    "attempt": attempt + 1,
                    "duration_ms": duration_ms,
                    "outcome": "error",
                },
            )
            raise RuntimeError(f"LLM unexpected error: {exc}") from exc

    # All retry attempts exhausted (only reachable via timeout path).
    logger.error(
        "llm call exhausted retries: %s after %s attempts",
        call_label,
        LLM_MAX_RETRIES + 1,
        extra={
            "llm_call": call_label,
            "total_attempts": LLM_MAX_RETRIES + 1,
            "outcome": "exhausted",
        },
    )
    raise RuntimeError(
        f"LLM call timed out after {LLM_MAX_RETRIES + 1} attempts"
    ) from last_exc


# ---------------------------------------------------------------------------
# Output sanitisation helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _sanitize_parsed_output(payload, safe_fallback: dict) -> dict:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_tailored_resume(
    resume_json: dict, job_description: str, debug: bool = False
) -> dict:
    """
    Tailor *resume_json* for *job_description* using the local Ollama model.

    Reliability guarantee
    ---------------------
    This function NEVER raises.  If the LLM is unavailable, times out, or
    returns unparseable output, it returns the original resume fields with
    ``[LLM_FAILED_FALLBACK]`` appended to the summary so callers always get
    a usable dict and the API always returns HTTP 200.
    """
    # Build the fallback from the original resume so no data is lost.
    original_summary = str(resume_json.get("summary", ""))
    original_experience = list(resume_json.get("experience", []))
    original_skills = list(resume_json.get("skills", []))

    # Normalise experience entries to strings for the response schema.
    def _entry_to_str(entry) -> str:
        if isinstance(entry, dict):
            return " ".join(str(v) for v in entry.values() if v)
        return str(entry)

    fallback_output = {
        "summary": f"{original_summary} {_FALLBACK_TAG}".strip(),
        "experience": [_entry_to_str(e) for e in original_experience],
        "skills": [str(s) for s in original_skills if s],
    }

    safe_fallback = {"summary": "", "experience": [], "skills": []}

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

    # --- Attempt 1: primary LLM call ---
    try:
        raw_output = _run_ollama(full_prompt, "tailor_resume")
    except Exception as exc:
        logger.error(
            "llm unavailable: tailor_resume returning fallback (%s)", exc,
            extra={"llm_call": "tailor_resume", "outcome": "fallback"},
        )
        return fallback_output

    if not raw_output:
        logger.error(
            "llm empty output: tailor_resume returning fallback",
            extra={"llm_call": "tailor_resume", "outcome": "fallback"},
        )
        return fallback_output

    raw_output = _extract_json_guard(raw_output)

    try:
        parsed_output = json.loads(raw_output)
        result = _sanitize_parsed_output(parsed_output, safe_fallback)
        if debug:
            logger.debug("tailor_resume parse success")
        return result
    except json.JSONDecodeError:
        pass  # fall through to correction attempt

    # --- Attempt 2: ask the model to fix its own malformed output ---
    correction_prompt = (
        "STRICTLY FIX THIS OUTPUT.\n"
        "Return ONLY valid JSON.\n"
        "No explanation.\n"
        "No markdown.\n"
        "Response MUST start with '{' and end with '}'.\n\n"
        f"{raw_output}"
    )

    try:
        retry_raw = _run_ollama(correction_prompt, "tailor_resume_correction")
    except Exception as exc:
        logger.error(
            "llm correction unavailable: tailor_resume returning fallback (%s)", exc,
            extra={"llm_call": "tailor_resume_correction", "outcome": "fallback"},
        )
        return fallback_output

    if not retry_raw:
        logger.error(
            "llm correction empty output: tailor_resume returning fallback",
            extra={"llm_call": "tailor_resume_correction", "outcome": "fallback"},
        )
        return fallback_output

    retry_raw = _extract_json_guard(retry_raw)

    try:
        retry_parsed = json.loads(retry_raw)
        result = _sanitize_parsed_output(retry_parsed, safe_fallback)
        if debug:
            logger.debug("tailor_resume correction parse success")
        return result
    except json.JSONDecodeError:
        logger.error(
            "llm output unparseable after correction: tailor_resume returning fallback",
            extra={"llm_call": "tailor_resume_correction", "outcome": "fallback"},
        )
        return fallback_output


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
