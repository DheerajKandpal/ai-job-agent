"""
test_auto_apply_properties.py — Property-based tests for the auto_apply package.

Uses Hypothesis to verify the 9 correctness properties defined in the design document.
All HTTP calls are mocked with unittest.mock.patch so tests are fast, deterministic,
and require no running server.
"""

import os
from unittest.mock import MagicMock, call, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from auto_apply.formatter import format_application

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# A strategy for a minimal valid job dict with all required fields
_job_required = {
    "id": st.text(min_size=1),
    "title": st.text(min_size=1),
    "company": st.text(),
    "description": st.text(),
    "link": st.text(),
}


def _job_strategy(**overrides):
    """Build a fixed_dictionaries strategy for a job dict, with optional field overrides."""
    fields = {**_job_required, **overrides}
    return st.fixed_dictionaries(fields)


def _make_ok_response(data: dict) -> MagicMock:
    """Return a mock requests.Response with status 200 and the given JSON data."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = data
    return mock_resp


def _make_fail_response(status: int = 500) -> MagicMock:
    """Return a mock requests.Response with a non-200 status code."""
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.text = "error"
    return mock_resp


# Default successful API responses
_TAILOR_OK = {"tailored_resume": "Tailored resume text"}
_COVER_LETTER_OK = {"cover_letter": "Cover letter text"}


# ---------------------------------------------------------------------------
# Property 1: format_application output shape
# Feature: auto-apply, Property 1: format_application output shape
# ---------------------------------------------------------------------------

@given(resume=st.text(), cover_letter=st.text())
@settings(max_examples=100)
def test_p1_format_application_output_shape(resume, cover_letter):
    # Feature: auto-apply, Property 1: format_application output shape
    result = format_application(resume, cover_letter)

    assert isinstance(result, dict), "format_application must return a dict"
    assert set(result.keys()) == {"resume_text", "cover_letter"}, (
        "format_application must return exactly keys {'resume_text', 'cover_letter'}"
    )
    assert isinstance(result["resume_text"], str), "resume_text must be a string"
    assert isinstance(result["cover_letter"], str), "cover_letter must be a string"
    assert result["resume_text"] == resume
    assert result["cover_letter"] == cover_letter


# ---------------------------------------------------------------------------
# Property 2: Jobs with no delivery method are always skipped
# Feature: auto-apply, Property 2: Jobs with no delivery method are always skipped
# ---------------------------------------------------------------------------

@given(
    job=_job_strategy(
        apply_email=st.one_of(st.none(), st.just("")),
        apply_endpoint=st.one_of(st.none(), st.just("")),
    )
)
@settings(max_examples=100)
def test_p2_no_delivery_method_skips_senders(job):
    # Feature: auto-apply, Property 2: Jobs with no delivery method are always skipped
    mock_post = MagicMock(side_effect=[
        _make_ok_response(_TAILOR_OK),
        _make_ok_response(_COVER_LETTER_OK),
    ])

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email") as mock_email, \
         patch("auto_apply.runner.send_to_endpoint") as mock_endpoint, \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        # Re-import to pick up patched env
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs([job])

    mock_email.assert_not_called()
    mock_endpoint.assert_not_called()


# ---------------------------------------------------------------------------
# Property 3: apply_email set → send_email called, send_to_endpoint not called
# Feature: auto-apply, Property 3: Jobs with apply_email always reach send_email
# ---------------------------------------------------------------------------

@given(
    job=_job_strategy(
        apply_email=st.text(min_size=1),
    )
)
@settings(max_examples=100)
def test_p3_apply_email_routes_to_send_email(job):
    # Feature: auto-apply, Property 3: Jobs with apply_email always reach send_email
    mock_post = MagicMock(side_effect=[
        _make_ok_response(_TAILOR_OK),
        _make_ok_response(_COVER_LETTER_OK),
    ])

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email") as mock_email, \
         patch("auto_apply.runner.send_to_endpoint") as mock_endpoint, \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs([job])

    mock_email.assert_called_once()
    mock_endpoint.assert_not_called()


# ---------------------------------------------------------------------------
# Property 4: apply_endpoint set (no apply_email) → send_to_endpoint called
# Feature: auto-apply, Property 4: Jobs with apply_endpoint always reach send_to_endpoint
# ---------------------------------------------------------------------------

@given(
    job=_job_strategy(
        apply_email=st.one_of(st.none(), st.just("")),
        apply_endpoint=st.text(min_size=1),
    )
)
@settings(max_examples=100)
def test_p4_apply_endpoint_routes_to_send_to_endpoint(job):
    # Feature: auto-apply, Property 4: Jobs with apply_endpoint always reach send_to_endpoint
    mock_post = MagicMock(side_effect=[
        _make_ok_response(_TAILOR_OK),
        _make_ok_response(_COVER_LETTER_OK),
    ])

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email") as mock_email, \
         patch("auto_apply.runner.send_to_endpoint") as mock_endpoint, \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs([job])

    mock_endpoint.assert_called_once()
    mock_email.assert_not_called()


# ---------------------------------------------------------------------------
# Property 5: Tailor failure → full pipeline skip
# Feature: auto-apply, Property 5: Tailor failure always skips the rest of the pipeline
# ---------------------------------------------------------------------------

@given(
    job=_job_strategy(apply_email=st.text(min_size=1)),
    fail_status=st.integers(min_value=400, max_value=599),
)
@settings(max_examples=100)
def test_p5_tailor_failure_skips_pipeline(job, fail_status):
    # Feature: auto-apply, Property 5: Tailor failure always skips the rest of the pipeline
    mock_post = MagicMock(return_value=_make_fail_response(fail_status))

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email") as mock_email, \
         patch("auto_apply.runner.send_to_endpoint") as mock_endpoint, \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs([job])

    # Only one call should have been made (the /tailor call); /cover-letter must not be called
    assert mock_post.call_count == 1, (
        f"Expected exactly 1 requests.post call (tailor only), got {mock_post.call_count}"
    )
    called_url = mock_post.call_args[0][0]
    assert "/tailor" in called_url, f"Expected /tailor call, got URL: {called_url}"
    mock_email.assert_not_called()
    mock_endpoint.assert_not_called()


# ---------------------------------------------------------------------------
# Property 6: Cover-letter failure → delivery skip
# Feature: auto-apply, Property 6: Cover-letter failure always skips delivery
# ---------------------------------------------------------------------------

@given(
    job=_job_strategy(apply_email=st.text(min_size=1)),
    fail_status=st.integers(min_value=400, max_value=599),
)
@settings(max_examples=100)
def test_p6_cover_letter_failure_skips_delivery(job, fail_status):
    # Feature: auto-apply, Property 6: Cover-letter failure always skips delivery
    mock_post = MagicMock(side_effect=[
        _make_ok_response(_TAILOR_OK),       # /tailor succeeds
        _make_fail_response(fail_status),    # /cover-letter fails
    ])

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email") as mock_email, \
         patch("auto_apply.runner.send_to_endpoint") as mock_endpoint, \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs([job])

    mock_email.assert_not_called()
    mock_endpoint.assert_not_called()


# ---------------------------------------------------------------------------
# Property 7: Missing API_KEY → ValueError before any requests.post call
# Feature: auto-apply, Property 7: Missing API_KEY always raises ValueError
# ---------------------------------------------------------------------------

@given(jobs=st.lists(
    _job_strategy(),
    max_size=5,
))
@settings(max_examples=100)
def test_p7_missing_api_key_raises_value_error(jobs):
    # Feature: auto-apply, Property 7: Missing API_KEY always raises ValueError
    mock_post = MagicMock()

    env_without_key = {k: v for k, v in os.environ.items() if k != "API_KEY"}

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch.dict(os.environ, env_without_key, clear=True):
        import auto_apply.runner as runner
        runner.API_KEY = None  # force unset

        with pytest.raises(ValueError):
            runner.process_jobs(jobs)

    mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Property 8: Every job in the list is processed exactly once
# Feature: auto-apply, Property 8: Every job in the list is processed exactly once
# ---------------------------------------------------------------------------

@given(
    jobs=st.lists(
        _job_strategy(apply_email=st.text(min_size=1)),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=100)
def test_p8_every_job_processed_exactly_once(jobs):
    # Feature: auto-apply, Property 8: Every job in the list is processed exactly once
    n = len(jobs)
    # Each job makes 2 requests.post calls: /tailor and /cover-letter
    responses = []
    for _ in jobs:
        responses.append(_make_ok_response(_TAILOR_OK))
        responses.append(_make_ok_response(_COVER_LETTER_OK))

    mock_post = MagicMock(side_effect=responses)

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email"), \
         patch("auto_apply.runner.send_to_endpoint"), \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs(jobs)

    assert mock_post.call_count == 2 * n, (
        f"Expected {2 * n} requests.post calls for {n} jobs, got {mock_post.call_count}"
    )


# ---------------------------------------------------------------------------
# Property 9: BASE_URL env var is reflected in all API request URLs
# Feature: auto-apply, Property 9: BASE_URL env var is reflected in all API request URLs
# ---------------------------------------------------------------------------

@given(
    base_url=st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_.:/")),
    job=_job_strategy(apply_email=st.text(min_size=1)),
)
@settings(max_examples=100)
def test_p9_base_url_used_in_all_requests(base_url, job):
    # Feature: auto-apply, Property 9: BASE_URL env var is reflected in all API request URLs
    mock_post = MagicMock(side_effect=[
        _make_ok_response(_TAILOR_OK),
        _make_ok_response(_COVER_LETTER_OK),
    ])

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email"), \
         patch("auto_apply.runner.send_to_endpoint"), \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key", "BASE_URL": base_url}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.BASE_URL = base_url
        runner.process_jobs([job])

    for c in mock_post.call_args_list:
        called_url = c[0][0]
        assert called_url.startswith(base_url), (
            f"Expected URL to start with BASE_URL '{base_url}', got '{called_url}'"
        )

# ---------------------------------------------------------------------------
# Property 10: Job cap enforced — never more than 20 jobs processed
# Feature: auto-apply, Property 10: Job cap is enforced — never more than 20 jobs processed
# ---------------------------------------------------------------------------

@given(
    extra=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50)
def test_p10_job_cap_enforced(extra, capsys):
    # Feature: auto-apply, Property 10: Job cap is enforced — never more than 20 jobs processed
    from auto_apply.rate_limiter import MAX_JOBS_PER_RUN

    n = MAX_JOBS_PER_RUN + extra  # always more than the cap
    jobs = [
        {
            "id": str(i),
            "title": f"Job {i}",
            "company": "Acme",
            "description": "desc",
            "link": "http://example.com",
            "apply_email": "hr@example.com",
        }
        for i in range(n)
    ]

    # Provide enough responses for up to MAX_JOBS_PER_RUN jobs (2 calls each)
    responses = []
    for _ in range(MAX_JOBS_PER_RUN):
        responses.append(_make_ok_response(_TAILOR_OK))
        responses.append(_make_ok_response(_COVER_LETTER_OK))

    mock_post = MagicMock(side_effect=responses)

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email"), \
         patch("auto_apply.runner.send_to_endpoint"), \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs(jobs)

    captured = capsys.readouterr()
    assert mock_post.call_count <= MAX_JOBS_PER_RUN * 2, (
        f"Expected at most {MAX_JOBS_PER_RUN * 2} API calls, got {mock_post.call_count}"
    )
    assert "Max job limit reached" in captured.out


# ---------------------------------------------------------------------------
# Property 11: should_continue returns False at or above the cap
# Feature: auto-apply, Property 11: should_continue returns False at or above the cap
# ---------------------------------------------------------------------------

@given(n=st.integers(min_value=0, max_value=30))
@settings(max_examples=100)
def test_p11_should_continue_boundary(n):
    # Feature: auto-apply, Property 11: should_continue returns False at or above the cap
    from auto_apply.rate_limiter import MAX_JOBS_PER_RUN, should_continue

    result = should_continue(n)
    expected = n < MAX_JOBS_PER_RUN
    assert result == expected, (
        f"should_continue({n}) returned {result}, expected {expected} "
        f"(MAX_JOBS_PER_RUN={MAX_JOBS_PER_RUN})"
    )


# ---------------------------------------------------------------------------
# Property 12: Sender retry — first failure triggers exactly one retry, job completes
# Feature: auto-apply, Property 12: Sender retry — first failure triggers exactly one retry
# ---------------------------------------------------------------------------

@given(job=_job_strategy(apply_email=st.text(min_size=1)))
@settings(max_examples=100)
def test_p12_sender_retry_first_failure_then_success(job, capsys):
    # Feature: auto-apply, Property 12: Sender retry — first failure triggers exactly one retry
    mock_post = MagicMock(side_effect=[
        _make_ok_response(_TAILOR_OK),
        _make_ok_response(_COVER_LETTER_OK),
    ])

    call_count = {"n": 0}

    def flaky_sender(j, p):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient failure")
        # second call succeeds silently

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email", side_effect=flaky_sender), \
         patch("auto_apply.runner.send_to_endpoint"), \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        runner.process_jobs([job])

    captured = capsys.readouterr()
    assert "Retrying..." in captured.out, "Expected 'Retrying...' in output"
    assert captured.out.count("Retrying...") == 1, "Expected exactly one retry log"
    assert "Completed job" in captured.out, "Expected job to complete after successful retry"


# ---------------------------------------------------------------------------
# Property 13: Sender retry — double failure logs failure and continues
# Feature: auto-apply, Property 13: Sender retry — double failure logs and continues
# ---------------------------------------------------------------------------

@given(
    jobs=st.lists(
        _job_strategy(apply_email=st.text(min_size=1)),
        min_size=2,
        max_size=3,
    )
)
@settings(max_examples=50)
def test_p13_sender_double_failure_logs_and_continues(jobs, capsys):
    # Feature: auto-apply, Property 13: Sender retry — double failure logs and continues
    n = len(jobs)
    responses = []
    for _ in jobs:
        responses.append(_make_ok_response(_TAILOR_OK))
        responses.append(_make_ok_response(_COVER_LETTER_OK))

    mock_post = MagicMock(side_effect=responses)

    def always_fail(j, p):
        raise RuntimeError("permanent failure")

    with patch("auto_apply.runner.requests.post", mock_post), \
         patch("auto_apply.runner.send_email", side_effect=always_fail), \
         patch("auto_apply.runner.send_to_endpoint"), \
         patch("auto_apply.runner.wait"), \
         patch.dict(os.environ, {"API_KEY": "test-key"}):
        import auto_apply.runner as runner
        runner.API_KEY = "test-key"
        # Should not raise — double failure must be swallowed
        runner.process_jobs(jobs)

    captured = capsys.readouterr()
    assert "Retrying..." in captured.out, "Expected 'Retrying...' in output"
    # All API calls should still have been attempted (pipeline continues after sender failure)
    assert mock_post.call_count == 2 * n, (
        f"Expected {2 * n} API calls for {n} jobs, got {mock_post.call_count}"
    )
