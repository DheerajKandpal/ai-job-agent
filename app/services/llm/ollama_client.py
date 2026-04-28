import json
import subprocess


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


def generate_tailored_resume(resume_json: dict, job_description: str) -> dict:
    resume_text = json.dumps(resume_json, ensure_ascii=True, indent=2)

    system_prompt = """
You are a resume optimization assistant.

STRICT RULES:
- Do NOT add new skills, tools, or experience
- Do NOT fabricate facts
- You ARE allowed to:
    - Rewrite bullet points to be more impactful
    - Use action verbs
    - Add metrics if already implied
    - Improve clarity and relevance

Return ONLY valid JSON.
""".strip()

    user_prompt = (
        f"Resume JSON:\n{resume_text}\n\n"
        f"Job Description:\n{job_description}\n\n"
        "TASK:\n"
        "- Improve bullet points\n"
        "- Highlight relevant skills\n"
        "- Keep facts EXACT\n"
        "- Return ONLY JSON (no explanation)"
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
        return resume_json

    if result.returncode != 0 or not result.stdout.strip():
        return resume_json

    json_block = _extract_json_block(result.stdout)
    if not json_block:
        return resume_json

    try:
        tailored_json = json.loads(json_block)
    except json.JSONDecodeError:
        return resume_json

    if not isinstance(tailored_json, dict):
        return resume_json

    if not _same_top_level_keys(resume_json, tailored_json):
        return resume_json

    original_skills = _collect_skills(resume_json)
    tailored_skills = _collect_skills(tailored_json)
    if not tailored_skills.issubset(original_skills):
        print("LLM rejected due to new skills")
        return resume_json

    print("LLM output accepted")
    return tailored_json


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
    print(json.dumps(tailored, indent=2))
