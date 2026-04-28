import json
import subprocess


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

    try:
        result = subprocess.run(
            ["ollama", "run", "qwen2.5-coder"],
            input=full_prompt,
            text=True,
            capture_output=True,
            check=False,
        )
    except (OSError, ValueError):
        return ""

    if result.returncode != 0:
        return ""

    return result.stdout.strip()
