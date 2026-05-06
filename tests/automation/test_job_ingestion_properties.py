"""
Property-based tests for automation/job_ingestion.py using Hypothesis.

Feature: real-job-ingestion-and-application

Each test corresponds to one of the correctness properties defined in the
design document (Properties 1–5).  All tests use @settings(max_examples=100).

Run with:
    pytest tests/automation/test_job_ingestion_properties.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from automation.job_ingestion import (
    compute_fingerprint,
    fetch_jobs,
    load_seen_jobs,
    save_seen_jobs,
    MockAdapter,
    APIAdapter,
    RSSAdapter,
)

# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

_nonempty_text = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())

_job_record_strategy = st.fixed_dictionaries(
    {
        "id": st.text(min_size=1, max_size=20),
        "title": _nonempty_text,
        "company": _nonempty_text,
        "job_description": st.text(min_size=50, max_size=300),
        "apply_link": st.just("https://example.com/job"),
        "source": st.just("mock"),
    }
)


def _make_mock_job(title: str = "Engineer", company: str = "Acme") -> dict:
    return {
        "id": "test-001",
        "title": title,
        "company": company,
        "job_description": "A" * 100,
        "apply_link": "https://example.com",
        "source": "mock",
    }


# ---------------------------------------------------------------------------
# Property 1: Source priority ordering is respected
# Feature: real-job-ingestion-and-application, Property 1: Source priority ordering is respected
# Validates: Requirements 1.2, 1.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    api_returns_results=st.booleans(),
    rss_returns_results=st.booleans(),
)
def test_source_priority_ordering(
    api_returns_results: bool,
    rss_returns_results: bool,
) -> None:
    """
    Property 1: fetch_jobs uses the highest-priority adapter that returns ≥ 1
    result and does NOT invoke lower-priority adapters once a result is found.
    """
    api_jobs = [_make_mock_job("API Job", "API Co")] if api_returns_results else []
    rss_jobs = [_make_mock_job("RSS Job", "RSS Co")] if rss_returns_results else []
    mock_jobs = [_make_mock_job("Mock Job", "Mock Co")]

    api_adapter = MagicMock()
    api_adapter.fetch.return_value = api_jobs

    rss_adapter = MagicMock()
    rss_adapter.fetch.return_value = rss_jobs

    mock_adapter = MagicMock()
    mock_adapter.fetch.return_value = mock_jobs

    priority_adapters = [
        ("api", api_adapter),
        ("rss", rss_adapter),
        ("mock", mock_adapter),
    ]

    with (
        patch("automation.job_ingestion._ADAPTER_PRIORITY", priority_adapters),
        patch("automation.job_ingestion._ADAPTER_MAP", {n: a for n, a in priority_adapters}),
        patch("automation.job_ingestion.load_seen_jobs", return_value=set()),
        patch("automation.job_ingestion.save_seen_jobs"),
    ):
        result = fetch_jobs(["api", "rss", "mock"], limit=10)

    if api_returns_results:
        # API adapter used; RSS and mock must NOT have been called
        api_adapter.fetch.assert_called_once()
        rss_adapter.fetch.assert_not_called()
        mock_adapter.fetch.assert_not_called()
        assert result[0]["title"] == "API Job"
    elif rss_returns_results:
        # RSS adapter used; mock must NOT have been called
        api_adapter.fetch.assert_called_once()
        rss_adapter.fetch.assert_called_once()
        mock_adapter.fetch.assert_not_called()
        assert result[0]["title"] == "RSS Job"
    else:
        # All real adapters empty; mock used
        api_adapter.fetch.assert_called_once()
        rss_adapter.fetch.assert_called_once()
        mock_adapter.fetch.assert_called_once()
        assert result[0]["title"] == "Mock Job"


# ---------------------------------------------------------------------------
# Property 2: fetch_jobs respects the limit parameter
# Feature: real-job-ingestion-and-application, Property 2: fetch_jobs respects the limit parameter
# Validates: Requirements 1.9
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(limit=st.integers(min_value=1, max_value=12))
def test_fetch_jobs_respects_limit(limit: int) -> None:
    """
    Property 2: for any positive integer limit, len(fetch_jobs(sources, limit)) <= limit.
    """
    with (
        patch("automation.job_ingestion.load_seen_jobs", return_value=set()),
        patch("automation.job_ingestion.save_seen_jobs"),
    ):
        result = fetch_jobs(["mock"], limit=limit)

    assert len(result) <= limit, (
        f"fetch_jobs returned {len(result)} records but limit was {limit}"
    )


# ---------------------------------------------------------------------------
# Property 3: Every returned Job_Record has all required fields populated
# Feature: real-job-ingestion-and-application, Property 3: Every returned Job_Record has all required fields populated
# Validates: Requirements 1.7
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(limit=st.integers(min_value=1, max_value=12))
def test_all_required_fields_populated(limit: int) -> None:
    """
    Property 3: every record returned by fetch_jobs has non-empty values for
    id, title, company, job_description, and apply_link.
    """
    with (
        patch("automation.job_ingestion.load_seen_jobs", return_value=set()),
        patch("automation.job_ingestion.save_seen_jobs"),
    ):
        result = fetch_jobs(["mock"], limit=limit)

    required_fields = ("id", "title", "company", "job_description", "apply_link")
    for job in result:
        for field in required_fields:
            assert field in job, f"Missing field '{field}' in job: {job}"
            assert job[field], (
                f"Field '{field}' is empty/falsy in job: {job}"
            )


# ---------------------------------------------------------------------------
# Property 4: Deduplication fingerprint is deterministic and correct
# Feature: real-job-ingestion-and-application, Property 4: Deduplication fingerprint is deterministic and correct
# Validates: Requirements 2.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(title=st.text(max_size=100), company=st.text(max_size=100))
def test_fingerprint_deterministic(title: str, company: str) -> None:
    """
    Property 4: compute_fingerprint is deterministic — calling it twice with
    the same inputs produces the same result.
    """
    fp1 = compute_fingerprint(title, company)
    fp2 = compute_fingerprint(title, company)
    assert fp1 == fp2, (
        f"Fingerprint not deterministic for title={title!r}, company={company!r}: "
        f"{fp1} != {fp2}"
    )


@settings(max_examples=100)
@given(title=st.text(max_size=100), company=st.text(max_size=100))
def test_fingerprint_correct_formula(title: str, company: str) -> None:
    """
    Property 4: compute_fingerprint equals SHA-256(title.lower().strip() + "|" +
    company.lower().strip()) as a hex digest.
    """
    expected_raw = title.lower().strip() + "|" + company.lower().strip()
    expected = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest()
    actual = compute_fingerprint(title, company)
    assert actual == expected, (
        f"Fingerprint mismatch for title={title!r}, company={company!r}: "
        f"got {actual}, expected {expected}"
    )


# ---------------------------------------------------------------------------
# Property 5: Deduplication round-trip — seen jobs filtered, new jobs stored
# Feature: real-job-ingestion-and-application, Property 5: Deduplication round-trip — seen jobs filtered, new jobs stored
# Validates: Requirements 2.2, 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    pre_seen_count=st.integers(min_value=0, max_value=6),
    limit=st.integers(min_value=1, max_value=12),
)
def test_deduplication_round_trip(pre_seen_count: int, limit: int) -> None:
    """
    Property 5: jobs whose fingerprints are already in the store are excluded
    from the output; new jobs' fingerprints are added to the store.
    """
    # Get the mock adapter's full job list
    mock_adapter = MockAdapter()
    all_mock_jobs = mock_adapter.fetch(12)

    # Pre-populate the seen store with fingerprints of the first `pre_seen_count` jobs
    pre_seen: set[str] = set()
    for job in all_mock_jobs[:pre_seen_count]:
        pre_seen.add(compute_fingerprint(job["title"], job["company"]))

    saved_fingerprints: set[str] = set()

    def fake_save(fps: set[str]) -> None:
        saved_fingerprints.update(fps)

    with (
        patch("automation.job_ingestion.load_seen_jobs", return_value=set(pre_seen)),
        patch("automation.job_ingestion.save_seen_jobs", side_effect=fake_save),
    ):
        result = fetch_jobs(["mock"], limit=limit)

    # All returned jobs must NOT have been in the pre-seen set
    for job in result:
        fp = compute_fingerprint(job["title"], job["company"])
        assert fp not in pre_seen, (
            f"Duplicate job returned: {job['title']} at {job['company']} "
            f"(fingerprint {fp} was in pre-seen set)"
        )

    # The saved fingerprints must include all returned jobs' fingerprints
    for job in result:
        fp = compute_fingerprint(job["title"], job["company"])
        assert fp in saved_fingerprints, (
            f"Fingerprint for returned job not saved: {job['title']} at {job['company']}"
        )


# ---------------------------------------------------------------------------
# Additional unit tests (example-based)
# ---------------------------------------------------------------------------

def test_mock_adapter_always_returns_data() -> None:
    """Mock adapter must always return data regardless of limit."""
    adapter = MockAdapter()
    result = adapter.fetch(5)
    assert len(result) == 5
    result_all = adapter.fetch(100)
    assert len(result_all) > 0


def test_api_adapter_stub_returns_empty() -> None:
    """API adapter stub returns empty list (no external dependencies)."""
    adapter = APIAdapter()
    assert adapter.fetch(10) == []


def test_rss_adapter_stub_returns_empty() -> None:
    """RSS adapter stub returns empty list (no external dependencies)."""
    adapter = RSSAdapter()
    assert adapter.fetch(10) == []


def test_fetch_jobs_zero_limit_returns_empty() -> None:
    """fetch_jobs with limit=0 returns empty list."""
    result = fetch_jobs(["mock"], limit=0)
    assert result == []


def test_fetch_jobs_unknown_source_falls_back_to_mock() -> None:
    """Unrecognised source name falls back to mock adapter."""
    with (
        patch("automation.job_ingestion.load_seen_jobs", return_value=set()),
        patch("automation.job_ingestion.save_seen_jobs"),
    ):
        result = fetch_jobs(["nonexistent_source"], limit=3)
    assert len(result) > 0


def test_seen_jobs_corrupt_file_initialises_empty(tmp_path: Path) -> None:
    """Corrupt seen_jobs.json initialises as empty set."""
    corrupt_file = tmp_path / "seen_jobs.json"
    corrupt_file.write_text("not valid json {{{")

    with patch("automation.job_ingestion.SEEN_JOBS_PATH", corrupt_file):
        result = load_seen_jobs()

    assert result == set()


def test_save_and_load_seen_jobs_round_trip(tmp_path: Path) -> None:
    """save_seen_jobs then load_seen_jobs returns the same fingerprints."""
    test_fps = {"abc123", "def456", "ghi789"}
    seen_path = tmp_path / "seen_jobs.json"

    with patch("automation.job_ingestion.SEEN_JOBS_PATH", seen_path):
        with patch("automation.job_ingestion._AUTOMATION_DIR", tmp_path):
            save_seen_jobs(test_fps)
        with patch("automation.job_ingestion.SEEN_JOBS_PATH", seen_path):
            loaded = load_seen_jobs()

    assert loaded == test_fps
