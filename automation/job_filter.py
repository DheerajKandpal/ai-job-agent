"""
job_filter.py
-------------
Filters a list of Job_Records, removing low-quality, spam, and role-excluded
postings before they enter the pipeline.

Public API
----------
    filter_jobs(jobs: list[Job_Record]) -> list[Job_Record]

Filter rules (applied in order)
--------------------------------
1. Description length < 50 characters → remove
2. All-caps title (title == title.upper() and only alpha/space chars) → remove
3. >5 consecutive punctuation chars OR punctuation ratio >0.20 → remove
4. Title or description contains a spam keyword (JOB_FILTER_SPAM_KEYWORDS) → remove
5. JOB_FILTER_ALLOWED_TITLES set → keep only records matching at least one keyword
6. JOB_FILTER_BLOCKED_TITLES set → remove records matching any keyword

Environment variables
---------------------
JOB_FILTER_SPAM_KEYWORDS    Comma-separated spam keywords (case-insensitive)
JOB_FILTER_ALLOWED_TITLES   Comma-separated allowed title keywords (case-insensitive)
JOB_FILTER_BLOCKED_TITLES   Comma-separated blocked title keywords (case-insensitive)
"""

from __future__ import annotations

import logging
import os
import re
import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automation.job_ingestion import Job_Record

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("automation.job_filter")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_DESCRIPTION_LENGTH = 50
_MAX_CONSECUTIVE_PUNCT = 5
_MAX_PUNCT_RATIO = 0.20

# Regex: 6 or more consecutive punctuation characters
_CONSECUTIVE_PUNCT_RE = re.compile(r"[^\w\s]{6,}")

_PUNCT_SET = set(string.punctuation)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_env_list(var: str) -> list[str]:
    """
    Read a comma-separated environment variable and return a list of
    non-empty, stripped, lower-cased keywords.
    """
    raw = os.getenv(var, "").strip()
    if not raw:
        return []
    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]


def _is_all_caps_title(title: str) -> bool:
    """
    Return True if the title consists entirely of uppercase letters and spaces
    (i.e. title == title.upper() and every non-space char is alphabetic).
    """
    if not title:
        return False
    # Must equal its own upper-case version
    if title != title.upper():
        return False
    # Must contain at least one letter (avoid flagging purely numeric/symbol titles)
    if not any(c.isalpha() for c in title):
        return False
    # Every character must be a letter or space
    return all(c.isalpha() or c == " " for c in title)


def _has_excessive_punctuation(text: str) -> bool:
    """
    Return True if `text` contains >5 consecutive punctuation characters
    OR if the ratio of punctuation characters to total characters exceeds 0.20.
    """
    if not text:
        return False
    # Check consecutive punctuation (>5 means 6+)
    if _CONSECUTIVE_PUNCT_RE.search(text):
        return True
    # Check punctuation ratio
    punct_count = sum(1 for c in text if c in _PUNCT_SET)
    ratio = punct_count / len(text)
    return ratio > _MAX_PUNCT_RATIO


def _contains_keyword(text: str, keywords: list[str]) -> bool:
    """Return True if `text` (lowercased) contains any of the keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def filter_jobs(jobs: list) -> list:
    """
    Filter a list of Job_Records, removing low-quality and spam postings.

    Parameters
    ----------
    jobs : list[Job_Record]
        Raw job records from fetch_jobs or any source.

    Returns
    -------
    list[Job_Record]
        Records that passed all filter rules.
    """
    spam_keywords = _get_env_list("JOB_FILTER_SPAM_KEYWORDS")
    allowed_titles = _get_env_list("JOB_FILTER_ALLOWED_TITLES")
    blocked_titles = _get_env_list("JOB_FILTER_BLOCKED_TITLES")

    removed_quality = 0
    removed_spam = 0
    removed_role = 0
    passed: list = []

    for job in jobs:
        title = job.get("title", "") or ""
        description = job.get("job_description", "") or ""

        # Rule 1: description too short
        if len(description) < _MIN_DESCRIPTION_LENGTH:
            removed_quality += 1
            logger.debug(
                "[FILTER] Removed '%s' at '%s' — description too short (%d chars)",
                title,
                job.get("company", ""),
                len(description),
            )
            continue

        # Rule 2: all-caps title
        if _is_all_caps_title(title):
            removed_quality += 1
            logger.debug(
                "[FILTER] Removed '%s' at '%s' — all-caps title",
                title,
                job.get("company", ""),
            )
            continue

        # Rule 3: excessive punctuation in title or description
        if _has_excessive_punctuation(title) or _has_excessive_punctuation(description):
            removed_quality += 1
            logger.debug(
                "[FILTER] Removed '%s' at '%s' — excessive punctuation",
                title,
                job.get("company", ""),
            )
            continue

        # Rule 4: spam keywords
        if spam_keywords and (
            _contains_keyword(title, spam_keywords)
            or _contains_keyword(description, spam_keywords)
        ):
            removed_spam += 1
            logger.debug(
                "[FILTER] Removed '%s' at '%s' — spam keyword match",
                title,
                job.get("company", ""),
            )
            continue

        # Rule 5: allowed titles (if configured, keep only matching)
        if allowed_titles and not _contains_keyword(title, allowed_titles):
            removed_role += 1
            logger.debug(
                "[FILTER] Removed '%s' at '%s' — not in allowed titles",
                title,
                job.get("company", ""),
            )
            continue

        # Rule 6: blocked titles
        if blocked_titles and _contains_keyword(title, blocked_titles):
            removed_role += 1
            logger.debug(
                "[FILTER] Removed '%s' at '%s' — blocked title",
                title,
                job.get("company", ""),
            )
            continue

        passed.append(job)

    total_removed = removed_quality + removed_spam + removed_role
    logger.info(
        "[FILTER] Removed %d jobs (quality: %d, spam: %d, role: %d) — %d passed",
        total_removed,
        removed_quality,
        removed_spam,
        removed_role,
        len(passed),
    )

    if not passed and jobs:
        logger.warning(
            "[FILTER] All jobs removed by filter — no records passed to pipeline"
        )

    return passed
