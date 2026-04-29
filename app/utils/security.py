import re


MAX_JOB_DESCRIPTION_LENGTH = 2000
PROMPT_INJECTION_PATTERNS = (
    "ignore instructions",
    "system prompt",
    "act as",
)


def validate_job_description(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("Job description is required")

    cleaned_text = "".join(character for character in text.strip() if character.isprintable())

    if not cleaned_text:
        raise ValueError("Job description cannot be empty")

    if len(cleaned_text) > MAX_JOB_DESCRIPTION_LENGTH:
        raise ValueError("Job description must be 2000 characters or fewer")

    return cleaned_text


def sanitize_prompt(text: str) -> str:
    if text is None:
        return ""

    normalized_text = re.sub(r"\s+", " ", text.lower()).strip()
    sanitized_text = text

    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern not in normalized_text:
            continue

        flexible_pattern = r"\s+".join(re.escape(part) for part in pattern.split())
        sanitized_text = re.sub(
            flexible_pattern,
            "",
            sanitized_text,
            flags=re.IGNORECASE,
        )

    return sanitized_text
