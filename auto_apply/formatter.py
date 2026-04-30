"""
formatter.py — Structures tailored resume and cover letter strings into a
unified application payload before delivery.
"""


def format_application(resume: str, cover_letter: str) -> dict:
    """
    Combine the tailored resume and cover letter into a single application payload.

    Args:
        resume: Plain-text tailored resume string.
        cover_letter: Plain-text cover letter string.

    Returns:
        A dict with exactly the keys 'resume_text' and 'cover_letter'.
    """
    return {
        "resume_text": resume,
        "cover_letter": cover_letter,
    }
