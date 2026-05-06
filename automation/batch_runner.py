"""
batch_runner.py
---------------
Runs the full job list through the parallel worker system and prints a
structured report.

Usage
-----
    python automation/batch_runner.py                          # all static jobs, 3 workers
    python automation/batch_runner.py --workers 5              # override concurrency
    python automation/batch_runner.py --jobs 3                 # run only first N jobs
    python automation/batch_runner.py --source mock --jobs 10  # fetch 10 mock jobs
    python automation/batch_runner.py --source mock            # fetch all mock jobs

When --source is provided, jobs are fetched via job_ingestion.fetch_jobs(),
filtered via job_filter.filter_jobs(), deduplicated, and then passed to the
pipeline. When --source is NOT provided, the existing static JOBS list is
used unchanged (backward-compatible behaviour).

automation/runner.py is preserved as the rollback path and must not be modified.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from pathlib import Path

from automation.worker import process_jobs_batch

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("automation.batch_runner")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Job list (same as runner.py — single source of truth kept here)
# ---------------------------------------------------------------------------

JOBS = [
    {
        "title": "Data Analyst",
        "company": "YipitData",
        "job_description": (
            "Analyze large alternative datasets, validate data quality, derive "
            "business insights, and support research workflows for clients using "
            "SQL, Excel, and analytical reasoning. Suitable for candidates with "
            "strong analytical skills and early data experience."
        ),
    },
    {
        "title": "Data QA Associate",
        "company": "YipitData",
        "job_description": (
            "Support merchant and vendor data quality operations, investigate "
            "anomalies, validate datasets, and maintain reliable data outputs. "
            "Good fit for 0-2 years of experience in data analysis, QA, Excel, "
            "SQL, or Python-based data checks."
        ),
    },
    {
        "title": "Data Quality Analyst II",
        "company": "HighLevel",
        "job_description": (
            "Work with revenue operations and data teams to improve CRM and "
            "business data quality, identify inconsistencies, run validation "
            "checks, and support data-driven decisions across an AI-powered "
            "SaaS platform."
        ),
    },
    {
        "title": "Backend Engineer",
        "company": "Soulside AI",
        "job_description": (
            "Build backend systems for an AI healthcare platform focused on "
            "reducing clinical documentation time. Responsibilities include API "
            "development, infrastructure work, product engineering, and "
            "collaboration with AI-driven workflow teams."
        ),
    },
    {
        "title": "Backend Engineer",
        "company": "SupplyHouse.com",
        "job_description": (
            "Develop backend and full-stack features for an e-commerce platform, "
            "improve internal systems, build scalable services, and collaborate "
            "with product and engineering teams on customer-facing and operational "
            "tools."
        ),
    },
    {
        "title": "Applied AI Engineer",
        "company": "Smart Working Solutions",
        "job_description": (
            "Design and implement AI solutions for document understanding, report "
            "generation, RAG pipelines, and API integrations. Work with "
            "unstructured data such as PDFs, documents, and images while "
            "collaborating with backend teams."
        ),
    },
    {
        "title": "AI Engineer - Forward Deployed Engineer",
        "company": "Deductive AI",
        "job_description": (
            "Work with customers to adapt and deploy AI SRE agents for production "
            "incident response. Responsibilities include customer discovery, "
            "platform configuration, AI workflow integration, and technical "
            "problem solving."
        ),
    },
    {
        "title": "Data Analyst - Fresher",
        "company": "PharmaForceIQ",
        "job_description": (
            "Support healthcare and life-sciences marketing analytics by cleaning "
            "data, preparing reports, tracking engagement metrics, and helping "
            "teams make data-driven decisions. Suitable for freshers with Excel, "
            "SQL, and analytical skills."
        ),
    },
    {
        "title": "Data Analyst",
        "company": "Gullak",
        "job_description": (
            "Join the growth team to analyze product and business data, build "
            "repeatable analyses, identify automation opportunities, and present "
            "insights to product, growth, and business stakeholders. Suitable "
            "for 0-2 years of experience."
        ),
    },
    {
        "title": "Junior Data Analyst",
        "company": "Trivora Systems",
        "job_description": (
            "Perform data analysis using Excel, Python, and SQL, identify trends "
            "and anomalies, build reports, and support data-driven "
            "decision-making. Designed for freshers or early-career analysts."
        ),
    },
]


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def _print_report(results: list[dict], total_s: float) -> None:
    print()
    print("=" * 70)
    print("BATCH PIPELINE REPORT")
    print("=" * 70)
    print(f"  Total jobs      : {len(results)}")
    print(f"  Total wall time : {total_s:.1f}s")
    print()

    # Per-job table
    header = (
        f"{'ID':>3}  {'Title':<35} {'Company':<20} {'Decision':<8} "
        f"{'Status':<10} {'Score':>6}  {'AppID':>6}  {'Time':>6}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        app_id = str(r["application_id"]) if r["application_id"] else "-"
        score  = f"{r['score']:.3f}" if r["score"] is not None else "-"
        dur    = f"{r['duration_s']:.1f}s"
        title  = (r["title"] or "")[:34]
        co     = (r["company"] or "")[:19]
        dec    = (r["decision"] or "-")[:8]
        status = r["status"][:10]
        print(
            f"{r['job_id']:>3}  {title:<35} {co:<20} {dec:<8} "
            f"{status:<10} {score:>6}  {app_id:>6}  {dur:>6}"
        )

    # Summary
    print()
    status_counts   = Counter(r["status"]                  for r in results)
    decision_counts = Counter((r["decision"] or "unknown") for r in results)
    print(f"  Status   : {dict(status_counts)}")
    print(f"  Decision : {dict(decision_counts)}")

    # Failures
    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        print()
        print("  FAILURES:")
        for r in failed:
            print(
                f"    job {r['job_id']} ({r['title']}): "
                f"failed_at={r['failed_at']}  error={r['error']}"
            )

    print("=" * 70)


# ---------------------------------------------------------------------------
# Job loading — static path vs. ingestion path
# ---------------------------------------------------------------------------

def _load_jobs_from_source(source: str, limit: int | None) -> list[dict]:
    """
    Fetch jobs via job_ingestion → job_filter pipeline.

    Returns a list of Job_Records ready for process_jobs_batch().
    Returns an empty list if no jobs survive deduplication + filtering.
    """
    # Import here so the module is importable without side effects when
    # --source is not used (avoids loading ingestion deps in static mode).
    from automation.job_ingestion import fetch_jobs
    from automation.job_filter import filter_jobs

    fetch_limit = limit if limit is not None else 50  # sensible default cap

    logger.info("[RUNNER] Fetching jobs from source '%s' (limit=%d)", source, fetch_limit)
    raw_jobs = fetch_jobs([source], fetch_limit)
    logger.info("[RUNNER] Fetched %d jobs from ingestion", len(raw_jobs))

    if not raw_jobs:
        logger.warning("[RUNNER] No jobs returned from source '%s' after deduplication", source)
        return []

    filtered_jobs = filter_jobs(raw_jobs)
    logger.info("[RUNNER] %d jobs after filtering", len(filtered_jobs))

    if not filtered_jobs:
        logger.warning("[RUNNER] No jobs remain after filtering — skipping pipeline")
        return []

    return filtered_jobs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel job batch runner")
    parser.add_argument(
        "--workers", type=int, default=3,
        help="Number of parallel worker threads (default: 3)",
    )
    parser.add_argument(
        "--jobs", type=int, default=None,
        help="Process only the first N jobs (default: all)",
    )
    parser.add_argument(
        "--stagger", type=float, default=0.5,
        help="Seconds between job submissions (default: 0.5)",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help=(
            "Job source to fetch from (e.g. 'mock', 'linkedin', 'indeed'). "
            "When provided, jobs are fetched via job_ingestion and filtered "
            "via job_filter. When omitted, the static JOBS list is used."
        ),
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Determine job list
    # ------------------------------------------------------------------
    if args.source:
        # Ingestion path: fetch → filter → deduplicate → pipeline
        jobs = _load_jobs_from_source(args.source, args.jobs)
        if not jobs:
            print(
                f"[RUNNER] No jobs to process from source '{args.source}' "
                "(all deduplicated or filtered). Exiting."
            )
            return
        # --jobs already applied inside _load_jobs_from_source via fetch limit;
        # apply again here as a hard cap in case filter returned more than requested.
        if args.jobs:
            jobs = jobs[: args.jobs]
    else:
        # Static path: backward-compatible, identical to original behaviour
        jobs = JOBS[: args.jobs] if args.jobs else JOBS

    print(
        f"Starting batch: {len(jobs)} jobs, {args.workers} workers, "
        f"{args.stagger}s stagger"
    )

    t_start = time.monotonic()
    results = process_jobs_batch(jobs, max_workers=args.workers, stagger_seconds=args.stagger)
    total_s = round(time.monotonic() - t_start, 2)

    _print_report(results, total_s)

    # Persist results
    output_path = Path(__file__).resolve().parent.parent / "run_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
