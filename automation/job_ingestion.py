"""
job_ingestion.py
----------------
Fetches, deduplicates, and returns Job_Records from priority-ordered sources.

Priority order: APIAdapter → RSSAdapter → MockAdapter
The first adapter that returns ≥ 1 result is used; lower-priority adapters
are not called once a result is found.

Deduplication is performed against a persistent fingerprint store
(automation/seen_jobs.json). Fingerprint = SHA-256(title.lower().strip() +
"|" + company.lower().strip()).

Public API
----------
    fetch_jobs(sources: list[str], limit: int) -> list[Job_Record]

Internal helpers (importable for testing)
-----------------------------------------
    compute_fingerprint(title: str, company: str) -> str
    load_seen_jobs() -> set[str]
    save_seen_jobs(fingerprints: set[str]) -> None
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("automation.job_ingestion")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_AUTOMATION_DIR = Path(__file__).resolve().parent
SEEN_JOBS_PATH = _AUTOMATION_DIR / "seen_jobs.json"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class Job_Record(TypedDict):
    id: str
    title: str
    company: str
    job_description: str
    apply_link: str
    source: str


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------


def compute_fingerprint(title: str, company: str) -> str:
    """
    Compute a SHA-256 deduplication fingerprint for a job.

    Fingerprint = SHA-256(title.lower().strip() + "|" + company.lower().strip())
    encoded as a hex digest.
    """
    raw = title.lower().strip() + "|" + company.lower().strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Deduplication store
# ---------------------------------------------------------------------------


def load_seen_jobs() -> set[str]:
    """
    Load the set of previously seen fingerprints from seen_jobs.json.
    Returns an empty set if the file is missing or corrupt.
    """
    if not SEEN_JOBS_PATH.exists():
        logger.warning("[DEDUP] seen_jobs.json not found — initialising as empty")
        return set()
    try:
        with open(SEEN_JOBS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        fingerprints = set(data.get("fingerprints", []))
        return fingerprints
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.warning("[DEDUP] seen_jobs.json corrupt (%s) — initialising as empty", exc)
        return set()


def save_seen_jobs(fingerprints: set[str]) -> None:
    """
    Persist the fingerprint set to seen_jobs.json using an atomic write
    (write to a temp file then rename) to prevent partial-write corruption.
    """
    data = {
        "fingerprints": sorted(fingerprints),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    # Write to a sibling temp file then rename for atomicity
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=_AUTOMATION_DIR, prefix=".seen_jobs_", suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, SEEN_JOBS_PATH)
    except OSError as exc:
        logger.error("[DEDUP] Failed to save seen_jobs.json: %s", exc)
        # Clean up temp file if rename failed
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class MockAdapter:
    """
    Always-available fallback adapter with 10+ realistic job records.
    Never raises; never makes external calls.
    """

    _MOCK_JOBS: list[Job_Record] = [
        {
            "id": "mock-001",
            "title": "Backend Engineer",
            "company": "Acme Corp",
            "job_description": (
                "Build and maintain scalable backend services using Python and FastAPI. "
                "Responsibilities include API design, database optimisation, and "
                "collaborating with frontend teams on integration. 2+ years experience "
                "with REST APIs and PostgreSQL required."
            ),
            "apply_link": "https://example.com/jobs/mock-001",
            "source": "mock",
        },
        {
            "id": "mock-002",
            "title": "Data Analyst",
            "company": "DataCo",
            "job_description": (
                "Analyse large datasets to derive business insights, build dashboards, "
                "and support data-driven decision-making. Proficiency in SQL, Python, "
                "and Tableau required. Experience with dbt or Airflow is a plus."
            ),
            "apply_link": "https://example.com/jobs/mock-002",
            "source": "mock",
        },
        {
            "id": "mock-003",
            "title": "Machine Learning Engineer",
            "company": "AI Startup",
            "job_description": (
                "Design and deploy ML models for production use cases including "
                "recommendation systems and NLP pipelines. Strong Python skills, "
                "experience with PyTorch or TensorFlow, and familiarity with MLOps "
                "tooling (MLflow, Kubeflow) required."
            ),
            "apply_link": "https://example.com/jobs/mock-003",
            "source": "mock",
        },
        {
            "id": "mock-004",
            "title": "Software Engineer",
            "company": "TechFirm",
            "job_description": (
                "Develop full-stack web applications using React and Node.js. "
                "Collaborate with product managers and designers to deliver features. "
                "Experience with TypeScript, REST APIs, and CI/CD pipelines required."
            ),
            "apply_link": "https://example.com/jobs/mock-004",
            "source": "mock",
        },
        {
            "id": "mock-005",
            "title": "DevOps Engineer",
            "company": "CloudOps Ltd",
            "job_description": (
                "Manage cloud infrastructure on AWS, implement CI/CD pipelines, and "
                "ensure system reliability. Experience with Terraform, Kubernetes, "
                "Docker, and monitoring tools such as Prometheus and Grafana required."
            ),
            "apply_link": "https://example.com/jobs/mock-005",
            "source": "mock",
        },
        {
            "id": "mock-006",
            "title": "Applied AI Engineer",
            "company": "NLP Labs",
            "job_description": (
                "Build AI-powered document processing pipelines using LLMs and RAG "
                "architectures. Work with unstructured data (PDFs, emails, contracts) "
                "and integrate with enterprise systems. Python, LangChain, and "
                "vector database experience required."
            ),
            "apply_link": "https://example.com/jobs/mock-006",
            "source": "mock",
        },
        {
            "id": "mock-007",
            "title": "Data Engineer",
            "company": "Pipeline Co",
            "job_description": (
                "Design and maintain data pipelines using Apache Spark and Airflow. "
                "Build data warehouses on Snowflake or BigQuery. Collaborate with "
                "analytics teams to ensure data quality and availability. 3+ years "
                "of data engineering experience required."
            ),
            "apply_link": "https://example.com/jobs/mock-007",
            "source": "mock",
        },
        {
            "id": "mock-008",
            "title": "Junior Data Analyst",
            "company": "Analytics Inc",
            "job_description": (
                "Support the analytics team by cleaning data, building reports, and "
                "identifying trends. Proficiency in Excel and SQL required; Python "
                "experience is a plus. Suitable for candidates with 0-2 years of "
                "experience in data analysis or business intelligence."
            ),
            "apply_link": "https://example.com/jobs/mock-008",
            "source": "mock",
        },
        {
            "id": "mock-009",
            "title": "Platform Engineer",
            "company": "Infra Systems",
            "job_description": (
                "Build and maintain internal developer platforms, improve deployment "
                "workflows, and reduce operational toil. Experience with Kubernetes, "
                "Helm, and GitOps practices required. Strong scripting skills in "
                "Python or Go preferred."
            ),
            "apply_link": "https://example.com/jobs/mock-009",
            "source": "mock",
        },
        {
            "id": "mock-010",
            "title": "AI Research Engineer",
            "company": "Research Labs",
            "job_description": (
                "Conduct applied research on large language models, fine-tuning "
                "strategies, and evaluation frameworks. Publish findings and "
                "collaborate with product teams to productionise research. PhD or "
                "equivalent experience in ML/NLP required."
            ),
            "apply_link": "https://example.com/jobs/mock-010",
            "source": "mock",
        },
        {
            "id": "mock-011",
            "title": "Full Stack Developer",
            "company": "WebWorks",
            "job_description": (
                "Build end-to-end web features across React frontend and Django "
                "backend. Participate in code reviews, write unit tests, and "
                "contribute to architecture decisions. 2+ years of full-stack "
                "development experience required."
            ),
            "apply_link": "https://example.com/jobs/mock-011",
            "source": "mock",
        },
        {
            "id": "mock-012",
            "title": "Data Quality Analyst",
            "company": "QualityFirst",
            "job_description": (
                "Validate data pipelines, investigate anomalies, and maintain "
                "data quality standards across the organisation. Experience with "
                "SQL, Python, and data profiling tools required. Familiarity with "
                "Great Expectations or dbt tests is a plus."
            ),
            "apply_link": "https://example.com/jobs/mock-012",
            "source": "mock",
        },
    ]

    def fetch(self, limit: int) -> list[Job_Record]:
        """Return up to `limit` mock job records. Always succeeds."""
        return self._MOCK_JOBS[:limit]


class APIAdapter:
    """
    Stub for structured API / data source integration.
    Returns an empty list until a real API integration is configured.
    """

    def fetch(self, limit: int) -> list[Job_Record]:  # noqa: ARG002
        """Fetch jobs from a structured API source. Currently a stub."""
        return []


class RSSAdapter:
    """
    Stub for RSS feed / job board integration.
    Returns an empty list until a real RSS integration is configured.
    """

    def fetch(self, limit: int) -> list[Job_Record]:  # noqa: ARG002
        """Fetch jobs from RSS feeds. Currently a stub."""
        return []


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

# Priority order: API → RSS → Mock
# Each entry is (source_name, adapter_instance)
_ADAPTER_PRIORITY: list[tuple[str, object]] = [
    ("api", APIAdapter()),
    ("rss", RSSAdapter()),
    ("mock", MockAdapter()),
]

_ADAPTER_MAP: dict[str, object] = {name: adapter for name, adapter in _ADAPTER_PRIORITY}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_jobs(sources: list[str], limit: int) -> list[Job_Record]:
    """
    Fetch up to `limit` Job_Records using a priority-based source strategy.

    Priority order: API → RSS → Mock
    The first adapter that returns ≥ 1 result is used; lower-priority adapters
    are not called once a result is found.

    Deduplication is applied against seen_jobs.json. New fingerprints are
    persisted before returning.

    Parameters
    ----------
    sources : list[str]
        Source names to consider (e.g. ["mock"], ["linkedin", "mock"]).
        Unrecognised source names are logged and skipped.
    limit : int
        Maximum number of Job_Records to return.

    Returns
    -------
    list[Job_Record]
        At most `limit` non-duplicate records.
    """
    if limit <= 0:
        return []

    # Determine which adapters to try, in priority order
    # Build ordered list: iterate _ADAPTER_PRIORITY and keep those in sources
    requested = set(s.lower() for s in sources)
    ordered_adapters: list[tuple[str, object]] = []
    for name, adapter in _ADAPTER_PRIORITY:
        if name in requested:
            ordered_adapters.append((name, adapter))

    # Warn about unrecognised source names
    known = {name for name, _ in _ADAPTER_PRIORITY}
    for s in sources:
        if s.lower() not in known:
            logger.warning("[INGEST] Unknown source '%s' — skipping", s)

    # If no recognised sources, fall back to mock
    if not ordered_adapters:
        logger.warning("[INGEST] No recognised sources — falling back to mock")
        ordered_adapters = [("mock", MockAdapter())]

    # Try adapters in priority order; stop at first that returns results
    raw_jobs: list[Job_Record] = []
    used_source = None
    for name, adapter in ordered_adapters:
        try:
            results = adapter.fetch(limit)  # type: ignore[attr-defined]
            if results:
                raw_jobs = results
                used_source = name
                logger.info("[INGEST] Fetched %d jobs from source '%s'", len(raw_jobs), name)
                break
            else:
                logger.info("[INGEST] Source '%s' returned 0 results — trying next", name)
        except Exception as exc:
            logger.error("[INGEST] Source '%s' failed: %s — trying next", name, exc)

    if not raw_jobs:
        logger.warning("[INGEST] All sources returned 0 results")
        return []

    # Deduplication
    seen = load_seen_jobs()
    new_jobs: list[Job_Record] = []
    duplicate_count = 0
    for job in raw_jobs:
        fp = compute_fingerprint(job["title"], job["company"])
        if fp in seen:
            duplicate_count += 1
        else:
            new_jobs.append(job)
            seen.add(fp)

    logger.info(
        "[INGEST] Deduplication: %d duplicates filtered, %d new jobs",
        duplicate_count,
        len(new_jobs),
    )

    # Enforce limit after deduplication
    new_jobs = new_jobs[:limit]

    # Persist updated fingerprint store
    if new_jobs:
        save_seen_jobs(seen)

    logger.info("[INGEST] Returning %d jobs (source: %s)", len(new_jobs), used_source)
    return new_jobs
