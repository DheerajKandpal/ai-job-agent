"""
audit_scoring.py — Scoring audit for the auto_apply job scoring system.

Evaluates 10 diverse job samples against score_job() and prints a ranked
summary with top/bottom observations.

Usage:
    python audit_scoring.py
"""

from auto_apply.scorer import score_job, THRESHOLD

# ---------------------------------------------------------------------------
# Sample jobs
# ---------------------------------------------------------------------------

JOBS = [
    # --- Highly relevant (3) ---
    {
        "id": "J001",
        "title": "Senior Data Analyst",
        "company": "DataCorp",
        "description": (
            "We are looking for a Senior Data Analyst with strong Python and SQL skills. "
            "You will build dashboards, perform data analysis, and work closely with "
            "engineering teams to deliver insights. Experience with pandas, numpy, and "
            "BI tools is a plus. You will own end-to-end data pipelines and present "
            "findings to stakeholders on a weekly basis."
        ),
        "apply_email": "jobs@datacorp.com",
        "apply_endpoint": "",
    },
    {
        "id": "J002",
        "title": "Data Analyst – Business Intelligence",
        "company": "Insightful Ltd",
        "description": (
            "Join our BI team as a Data Analyst. You will write complex SQL queries, "
            "develop Python scripts for data transformation, and maintain our analytics "
            "dashboard. Strong understanding of data modelling and analysis techniques "
            "required. We value curiosity, attention to detail, and the ability to "
            "communicate data-driven findings clearly to non-technical audiences."
        ),
        "apply_email": "",
        "apply_endpoint": "https://insightful.io/apply",
    },
    {
        "id": "J003",
        "title": "Junior Data Analyst",
        "company": "StartupAI",
        "description": (
            "Great entry-level opportunity for a data analyst. You will use Python and "
            "SQL daily to clean datasets, run analysis, and contribute to our reporting "
            "dashboard. We work with large volumes of data and expect you to be "
            "comfortable writing scripts to automate repetitive tasks. Mentorship "
            "provided. Remote-friendly role with flexible hours."
        ),
        "apply_email": "hire@startupai.com",
        "apply_endpoint": "",
    },

    # --- Medium relevance (3) ---
    {
        "id": "J004",
        "title": "Business Intelligence Developer",
        "company": "RetailMetrics",
        "description": (
            "We need a BI Developer to design and maintain reporting solutions. "
            "Experience with SQL and dashboard tools (Tableau, Power BI) is required. "
            "You will collaborate with data teams to translate business requirements "
            "into visual reports. Some scripting experience is helpful but not mandatory. "
            "This role sits within our data platform team."
        ),
        "apply_email": "careers@retailmetrics.com",
        "apply_endpoint": "",
    },
    {
        "id": "J005",
        "title": "Analytics Engineer",
        "company": "CloudBase",
        "description": (
            "Analytics Engineer role focused on building reliable data pipelines. "
            "You will work with dbt, SQL, and cloud data warehouses. Some Python "
            "scripting is expected. You will partner with analysts to ensure data "
            "quality and availability. Familiarity with data modelling best practices "
            "and version control is required for this position."
        ),
        "apply_email": "",
        "apply_endpoint": "https://cloudbase.io/jobs/ae",
    },
    {
        "id": "J006",
        "title": "Reporting Specialist",
        "company": "FinanceGroup",
        "description": (
            "Reporting Specialist needed to produce weekly and monthly management "
            "reports. You will use Excel and SQL to extract and present data. "
            "Experience with financial data and analysis is preferred. The role "
            "involves working with multiple stakeholders to gather requirements and "
            "deliver accurate, timely reports. Attention to detail is essential."
        ),
        "apply_email": "apply@financegroup.com",
        "apply_endpoint": "",
    },

    # --- Irrelevant (2) ---
    {
        "id": "J007",
        "title": "Regional Sales Manager",
        "company": "SalesForce Partners",
        "description": (
            "We are hiring a Regional Sales Manager to drive revenue growth across "
            "the EMEA region. You will manage a team of account executives, develop "
            "territory plans, and build relationships with enterprise clients. "
            "Strong negotiation skills and a proven track record in B2B sales are "
            "required. CRM experience and excellent communication skills are a must."
        ),
        "apply_email": "sales-jobs@sfpartners.com",
        "apply_endpoint": "",
    },
    {
        "id": "J008",
        "title": "Digital Marketing Manager",
        "company": "BrandBoost",
        "description": (
            "BrandBoost is looking for a Digital Marketing Manager to lead our online "
            "campaigns. You will manage SEO, SEM, social media, and email marketing "
            "channels. Experience with Google Ads, Meta Ads, and marketing automation "
            "platforms is required. Creative thinking and strong copywriting skills "
            "are essential. You will report directly to the CMO."
        ),
        "apply_email": "",
        "apply_endpoint": "https://brandboost.com/careers/dmm",
    },

    # --- Edge cases (2) ---
    {
        "id": "J009",
        "title": "Data Analyst",
        "company": "",           # missing company — no bonus
        "description": "Python SQL",  # short description (≤200 chars) — no length pts
        "apply_email": "short@example.com",
        "apply_endpoint": "",
    },
    {
        "id": "J010",
        "title": "",             # missing title — no title pts
        "company": "",           # missing company
        "description": "",       # missing description
        # missing apply_email and apply_endpoint
    },
]

# ---------------------------------------------------------------------------
# Score all jobs
# ---------------------------------------------------------------------------

results = []
for job in JOBS:
    score = score_job(job)
    results.append({
        "id": job.get("id", "?"),
        "title": job.get("title") or "(no title)",
        "score": score,
    })

# Sort highest → lowest
results.sort(key=lambda r: r["score"], reverse=True)

# ---------------------------------------------------------------------------
# Print ranked table
# ---------------------------------------------------------------------------

COL_ID    = 6
COL_SCORE = 7
COL_TITLE = 42

header = f"{'ID':<{COL_ID}} {'TITLE':<{COL_TITLE}} {'SCORE':>{COL_SCORE}}"
divider = "-" * len(header)

print()
print("=" * len(header))
print("  JOB SCORING AUDIT")
print(f"  Threshold: {THRESHOLD:.0f} pts  |  Jobs evaluated: {len(results)}")
print("=" * len(header))
print()
print(header)
print(divider)

for r in results:
    flag = " ✓" if r["score"] >= THRESHOLD else " ✗"
    title_display = r["title"][:COL_TITLE]
    print(f"{r['id']:<{COL_ID}} {title_display:<{COL_TITLE}} {r['score']:>{COL_SCORE}.1f}{flag}")

print(divider)
print(f"  ✓ = score >= {THRESHOLD:.0f} (would be processed)   ✗ = score < {THRESHOLD:.0f} (would be skipped)")
print()

# ---------------------------------------------------------------------------
# Observation block
# ---------------------------------------------------------------------------

print("=" * len(header))
print("  OBSERVATIONS")
print("=" * len(header))

print()
print("  TOP 3 JOBS:")
for i, r in enumerate(results[:3], start=1):
    print(f"    {i}. [{r['id']}] {r['title']} — {r['score']:.1f} pts")

print()
print("  BOTTOM 3 JOBS:")
for i, r in enumerate(results[-3:], start=1):
    print(f"    {i}. [{r['id']}] {r['title']} — {r['score']:.1f} pts")

print()
above = sum(1 for r in results if r["score"] >= THRESHOLD)
below = len(results) - above
print(f"  SUMMARY: {above} job(s) above threshold, {below} job(s) below threshold.")
print()
