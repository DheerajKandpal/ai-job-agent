"""
test_runner.py — End-to-end smoke test for the auto_apply pipeline.

Runs process_jobs() against three representative jobs:
  1. Email job   — delivery via send_email (SMTP stubbed)
  2. Endpoint job — delivery via send_to_endpoint (real POST to httpbin.org)
  3. Invalid job  — no apply_email / apply_endpoint → skipped

External dependencies that would block a local run are monkey-patched:
  - /tailor and /cover-letter API calls → return canned responses
  - /applications/{id} PATCH → returns 200
  - send_email → stubbed (avoids needing real SMTP credentials)
  - rate_limiter.wait → no-op (avoids 30–60 s sleep between jobs)

Run with:
    API_KEY=test python test_runner.py
"""

import os
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure API_KEY is set so process_jobs doesn't raise immediately
# ---------------------------------------------------------------------------
if not os.getenv("API_KEY"):
    os.environ["API_KEY"] = "test-key"

# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

JOBS = [
    # Job 1 — email delivery
    {
        "id": "job-001",
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "description": "Build scalable Python services.",
        "link": "https://example.com/jobs/001",
        "apply_email": "hiring@acme.com",
    },
    # Job 2 — endpoint delivery (real POST to httpbin.org/post)
    {
        "id": "job-002",
        "title": "Senior Python Developer",
        "company": "Globex",
        "description": "Lead backend architecture.",
        "link": "https://example.com/jobs/002",
        "apply_endpoint": "https://httpbin.org/post",
    },
    # Job 3 — no delivery method → should be skipped
    {
        "id": "job-003",
        "title": "Data Engineer",
        "company": "Initech",
        "description": "Build data pipelines.",
        "link": "https://example.com/jobs/003",
    },
]

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------

def _make_response(status: int, json_data: dict) -> MagicMock:
    """Return a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _stub_requests_post(url: str, **kwargs) -> MagicMock:
    """
    Intercept requests.post calls made by runner._post and endpoint_sender.

    - /tailor          → canned tailored resume
    - /cover-letter    → canned cover letter
    - httpbin.org/post → pass through to the real network (via a fresh Session)
    - anything else    → 200 OK
    """
    if "/tailor" in url:
        return _make_response(200, {"tailored_resume": "Experienced Python engineer with 5+ years."})
    if "/cover-letter" in url:
        return _make_response(200, {"cover_letter": "Dear Hiring Manager, I am excited to apply..."})
    if "httpbin.org" in url:
        # Use a Session to bypass the module-level patch on requests.post
        import requests as _requests
        with _requests.Session() as session:
            return session.post(url, **kwargs)
    # Fallback (e.g. any other POST)
    return _make_response(200, {"ok": True})


def _stub_requests_patch(url: str, **kwargs) -> MagicMock:
    """Stub PATCH /applications/{id} — always succeeds."""
    return _make_response(200, {"status": "applied"})


def _stub_send_email(job: dict, payload: dict) -> None:
    """Stub send_email — simulates a successful send without real SMTP."""
    print(f"[STUB] send_email → to={job['apply_email']} subject='Job Application – {job['title']}'")
    print("Email sent successfully")


def _stub_wait() -> None:
    """Stub wait() — skips the 30–60 s inter-job delay."""
    pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("auto_apply end-to-end smoke test")
    print("=" * 60)
    print()

    import auto_apply.runner as runner

    # Patch at the module level so all internal calls are intercepted
    with (
        patch.object(runner.requests, "post", side_effect=_stub_requests_post),
        patch.object(runner.requests, "patch", side_effect=_stub_requests_patch),
        patch.object(runner, "send_email", side_effect=_stub_send_email),
        patch.object(runner, "wait", side_effect=_stub_wait),
    ):
        # Force runner to re-read API_KEY (it reads at import time)
        runner.API_KEY = os.environ["API_KEY"]

        try:
            runner.process_jobs(JOBS)
        except Exception as exc:
            print(f"\n[ERROR] process_jobs raised an unexpected exception: {exc}", file=sys.stderr)
            sys.exit(1)

    print()
    print("=" * 60)
    print("Smoke test complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
