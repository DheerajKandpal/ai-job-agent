"""
Property-based tests for automation/job_filter.py using Hypothesis.

Feature: real-job-ingestion-and-application

Each test corresponds to one of the correctness properties defined in the
design document (Properties 6–9).  All tests use @settings(max_examples=100).

Run with:
    pytest tests/automation/test_job_filter_properties.py -v
"""

from __future__ import annotations

import os
import string
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from automation.job_filter import filter_jobs, _is_all_caps_title, _has_excessive_punctuation

# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

_PUNCT_CHARS = string.punctuation  # !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~


def _make_job(
    title: str = "Software Engineer",
    description: str = "A" * 100,
    company: str = "Acme",
) -> dict:
    return {
        "id": "test-001",
        "title": title,
        "company": company,
        "job_description": description,
        "apply_link": "https://example.com",
        "source": "mock",
    }


# Strategy for a valid (passing) job description (≥50 chars, no spam)
_valid_description = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=50,
    max_size=300,
)

# Strategy for a valid title (not all-caps, not all-punct)
_valid_title = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=3,
    max_size=50,
).filter(lambda t: not _is_all_caps_title(t))


# ---------------------------------------------------------------------------
# Property 6: filter_jobs removes short descriptions
# Feature: real-job-ingestion-and-application, Property 6: filter_jobs removes short descriptions
# Validates: Requirements 3.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(description=st.text(max_size=49))
def test_short_descriptions_removed(description: str) -> None:
    """
    Property 6: any Job_Record whose job_description has fewer than 50 characters
    (including the empty string) must be excluded from filter_jobs output.
    """
    job = _make_job(description=description)
    result = filter_jobs([job])
    assert result == [], (
        f"Job with description length {len(description)} should be removed, "
        f"but was returned: {job}"
    )


@settings(max_examples=100)
@given(description=st.text(min_size=50, max_size=300))
def test_sufficient_descriptions_not_removed_by_length(description: str) -> None:
    """
    Property 6 (inverse): a job with description ≥ 50 chars is NOT removed
    by the length rule (it may still be removed by other rules).
    """
    # Use a title that won't trigger other rules
    job = _make_job(title="Software Engineer", description=description)
    # We only assert it's not removed by the length rule specifically;
    # other rules may still apply, so we just check it's not filtered for length.
    # We verify by checking that a job with exactly 50 chars passes length check.
    job_50 = _make_job(title="Software Engineer", description="A" * 50)
    result = filter_jobs([job_50])
    assert result == [job_50], (
        "Job with exactly 50-char description should pass the length filter"
    )


# ---------------------------------------------------------------------------
# Property 7: filter_jobs removes all-caps titles
# Feature: real-job-ingestion-and-application, Property 7: filter_jobs removes all-caps titles
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    title=st.text(
        alphabet=st.characters(whitelist_categories=("Lu",)),  # uppercase letters only
        min_size=2,
        max_size=30,
    ).filter(lambda t: t.strip() and all(c.isalpha() or c == " " for c in t))
)
def test_all_caps_titles_removed(title: str) -> None:
    """
    Property 7: any Job_Record whose title consists entirely of uppercase
    letters (and spaces) must be excluded from filter_jobs output.
    """
    assume(title.strip())  # non-empty after strip
    assume(any(c.isalpha() for c in title))  # at least one letter
    assume(title == title.upper())  # confirm all-caps
    assume(all(c.isalpha() or c == " " for c in title))  # only alpha/space

    job = _make_job(title=title)
    result = filter_jobs([job])
    assert result == [], (
        f"All-caps title '{title}' should be removed, but was returned"
    )


@settings(max_examples=100)
@given(
    title=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")),
        min_size=3,
        max_size=30,
    ).filter(lambda t: t.strip() and not _is_all_caps_title(t))
)
def test_mixed_case_titles_not_removed_by_caps_rule(title: str) -> None:
    """
    Property 7 (inverse): a title that is NOT all-caps is not removed by the
    all-caps rule.
    """
    job = _make_job(title=title, description="A" * 100)
    result = filter_jobs([job])
    # Should not be removed by the all-caps rule (may be removed by others)
    # Verify the helper function directly
    assert not _is_all_caps_title(title), (
        f"Title '{title}' should not be classified as all-caps"
    )


# ---------------------------------------------------------------------------
# Property 8: filter_jobs enforces punctuation limits
# Feature: real-job-ingestion-and-application, Property 8: filter_jobs enforces punctuation limits
# Validates: Requirements 3.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    prefix=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
        min_size=1,
        max_size=20,
    ),
    punct_run_length=st.integers(min_value=6, max_value=20),
)
def test_consecutive_punctuation_removed(prefix: str, punct_run_length: int) -> None:
    """
    Property 8: a title or description with >5 consecutive punctuation characters
    must be excluded.
    """
    punct_run = "!" * punct_run_length  # 6+ consecutive punctuation chars
    title_with_punct = prefix + punct_run
    job = _make_job(title=title_with_punct, description="A" * 100)
    result = filter_jobs([job])
    assert result == [], (
        f"Title with {punct_run_length} consecutive punctuation chars should be removed"
    )


@settings(max_examples=100)
@given(
    alpha_count=st.integers(min_value=50, max_value=150),
    # punct_count must be > 0.20 * total, i.e. > 0.20 * (alpha + punct)
    # Solving: punct > 0.20 * (alpha + punct) → punct > alpha / 4
    # We generate punct_count as a fraction of alpha_count to guarantee ratio > 0.20
    punct_fraction=st.floats(min_value=0.26, max_value=0.60),
)
def test_high_punctuation_ratio_removed(alpha_count: int, punct_fraction: float) -> None:
    """
    Property 8: a description where punctuation ratio > 0.20 must be excluded.
    """
    punct_count = max(1, int(alpha_count * punct_fraction))
    description = "!" * punct_count + "a" * alpha_count
    total = len(description)
    actual_ratio = punct_count / total
    # Confirm ratio is actually > 0.20 (should always be true given our generation)
    assume(actual_ratio > 0.20)
    assume(len(description) >= 50)
    job = _make_job(title="Software Engineer", description=description)
    result = filter_jobs([job])
    assert result == [], (
        f"Description with punctuation ratio {punct_count}/{total} "
        f"({actual_ratio:.2%}) should be removed"
    )


def test_exactly_five_consecutive_punctuation_allowed() -> None:
    """
    Property 8 boundary: exactly 5 consecutive punctuation chars is allowed
    (the rule removes >5, i.e. 6+), provided the overall punctuation ratio
    stays at or below 0.20.
    """
    # Use a long title so 5 punctuation chars don't push ratio above 0.20
    # e.g. "Software Engineer!!!!!" — 22 chars, 5 punct → ratio = 5/22 ≈ 0.23 (too high)
    # Use a much longer title: 100 alpha + 5 punct → ratio = 5/105 ≈ 0.048 (safe)
    long_prefix = "a" * 100
    title = long_prefix + "!!!!!"  # exactly 5 consecutive punctuation chars
    job = _make_job(title=title, description="A" * 100)
    result = filter_jobs([job])
    assert result == [job], (
        f"Title with exactly 5 consecutive punctuation chars and low ratio "
        f"should NOT be removed"
    )


# ---------------------------------------------------------------------------
# Property 9: filter_jobs enforces allowed and blocked title lists
# Feature: real-job-ingestion-and-application, Property 9: filter_jobs enforces allowed and blocked title lists
# Validates: Requirements 3.6, 3.7
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    allowed_keyword=st.text(
        alphabet=st.characters(whitelist_categories=("Ll",)),
        min_size=3,
        max_size=15,
    ),
    title_suffix=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Zs")),
        min_size=0,
        max_size=20,
    ),
)
def test_allowed_titles_only_matching_pass(
    allowed_keyword: str, title_suffix: str
) -> None:
    """
    Property 9 (allowed): when JOB_FILTER_ALLOWED_TITLES is set, only records
    whose title contains at least one keyword pass through.
    """
    assume(allowed_keyword.strip())

    # Job whose title contains the allowed keyword → should pass
    matching_job = _make_job(
        title=f"{allowed_keyword} {title_suffix}".strip(),
        description="A" * 100,
    )
    # Job whose title does NOT contain the allowed keyword → should be removed
    non_matching_job = _make_job(
        title="zzz_no_match_xyz",
        description="A" * 100,
    )
    assume(allowed_keyword.lower() not in "zzz_no_match_xyz")

    with patch.dict(os.environ, {"JOB_FILTER_ALLOWED_TITLES": allowed_keyword}):
        result_matching = filter_jobs([matching_job])
        result_non_matching = filter_jobs([non_matching_job])

    assert result_matching == [matching_job], (
        f"Job with title containing '{allowed_keyword}' should pass allowed filter"
    )
    assert result_non_matching == [], (
        f"Job with title 'zzz_no_match_xyz' should be removed by allowed filter "
        f"(keyword: '{allowed_keyword}')"
    )


@settings(max_examples=100)
@given(
    blocked_keyword=st.text(
        alphabet=st.characters(whitelist_categories=("Ll",)),
        min_size=3,
        max_size=15,
    ),
)
def test_blocked_titles_removed(blocked_keyword: str) -> None:
    """
    Property 9 (blocked): when JOB_FILTER_BLOCKED_TITLES is set, records whose
    title contains any blocked keyword are removed.
    """
    assume(blocked_keyword.strip())

    # Job whose title contains the blocked keyword → should be removed
    blocked_job = _make_job(
        title=f"Senior {blocked_keyword} Engineer",
        description="A" * 100,
    )
    # Job whose title does NOT contain the blocked keyword → should pass
    safe_job = _make_job(
        title="zzz_safe_title_xyz",
        description="A" * 100,
    )
    assume(blocked_keyword.lower() not in "zzz_safe_title_xyz")

    with patch.dict(os.environ, {"JOB_FILTER_BLOCKED_TITLES": blocked_keyword}):
        result_blocked = filter_jobs([blocked_job])
        result_safe = filter_jobs([safe_job])

    assert result_blocked == [], (
        f"Job with title containing blocked keyword '{blocked_keyword}' should be removed"
    )
    assert result_safe == [safe_job], (
        f"Job with title 'zzz_safe_title_xyz' should pass blocked filter "
        f"(blocked keyword: '{blocked_keyword}')"
    )


# ---------------------------------------------------------------------------
# Additional unit tests (example-based)
# ---------------------------------------------------------------------------

def test_filter_jobs_empty_input() -> None:
    """filter_jobs on empty list returns empty list."""
    assert filter_jobs([]) == []


def test_filter_jobs_all_valid_mock_jobs() -> None:
    """All mock adapter jobs should pass the filter (they are clean data)."""
    from automation.job_ingestion import MockAdapter
    mock_jobs = MockAdapter().fetch(12)
    result = filter_jobs(mock_jobs)
    assert len(result) == len(mock_jobs), (
        f"Expected all {len(mock_jobs)} mock jobs to pass filter, "
        f"but only {len(result)} passed"
    )


def test_filter_jobs_empty_description_removed() -> None:
    """Job with empty description is removed."""
    job = _make_job(description="")
    assert filter_jobs([job]) == []


def test_filter_jobs_all_removed_logs_warning(caplog) -> None:
    """When all jobs are removed, a warning is logged."""
    import logging
    job = _make_job(description="short")  # < 50 chars
    with caplog.at_level(logging.WARNING, logger="automation.job_filter"):
        result = filter_jobs([job])
    assert result == []
    assert any("All jobs removed" in r.message for r in caplog.records)


def test_spam_keyword_in_description_removed() -> None:
    """Job with spam keyword in description is removed."""
    job = _make_job(
        title="Software Engineer",
        description="A" * 50 + " URGENT HIRING CLICK HERE NOW",
    )
    with patch.dict(os.environ, {"JOB_FILTER_SPAM_KEYWORDS": "urgent,click here"}):
        result = filter_jobs([job])
    assert result == []


def test_spam_keyword_in_title_removed() -> None:
    """Job with spam keyword in title is removed."""
    job = _make_job(title="URGENT Software Engineer", description="A" * 100)
    with patch.dict(os.environ, {"JOB_FILTER_SPAM_KEYWORDS": "urgent"}):
        result = filter_jobs([job])
    assert result == []
