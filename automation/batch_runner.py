"""
batch_runner.py
---------------
Runs the full job list through the parallel worker system and prints a
structured report.

Usage
-----
    python automation/batch_runner.py              # all 10 jobs, 3 workers
    python automation/batch_runner.py --workers 5  # override concurrency
    python automation/batch_runner.py --jobs 3     # run only first N jobs
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from automation.worker import process_jobs_batch

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
    header = f"{'ID':>3}  {'Title':<35} {'Company':<20} {'Decision':<8} {'Status':<10} {'Score':>6}  {'AppID':>6}  {'Time':>6}"
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
        print(f"{r['job_id']:>3}  {title:<35} {co:<20} {dec:<8} {status:<10} {score:>6}  {app_id:>6}  {dur:>6}")

    # Summary
    print()
    status_counts   = Counter(r["status"]                    for r in results)
    decision_counts = Counter((r["decision"] or "unknown")   for r in results)
    print(f"  Status   : {dict(status_counts)}")
    print(f"  Decision : {dict(decision_counts)}")

    # Failures
    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        print()
        print("  FAILURES:")
        for r in failed:
            print(f"    job {r['job_id']} ({r['title']}): failed_at={r['failed_at']}  error={r['error']}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel job batch runner")
    parser.add_argument("--workers", type=int, default=3,
                        help="Number of parallel worker threads (default: 3)")
    parser.add_argument("--jobs", type=int, default=None,
                        help="Process only the first N jobs (default: all)")
    parser.add_argument("--stagger", type=float, default=0.5,
                        help="Seconds between job submissions (default: 0.5)")
    args = parser.parse_args()

    jobs = JOBS[: args.jobs] if args.jobs else JOBS

    print(f"Starting batch: {len(jobs)} jobs, {args.workers} workers, "
          f"{args.stagger}s stagger")

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
