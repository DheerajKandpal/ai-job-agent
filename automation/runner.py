import json
import os
import requests
import sys
from collections import Counter
from datetime import datetime, timezone

from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root (important fix)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")



BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise RuntimeError("Missing API_KEY — check .env loading")

headers = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json",
}

# Decision tiers mirror app/services/match_service.py thresholds.
# No threshold env var needed — the backend classifies for us.
VALID_DECISIONS = {"HIGH", "MEDIUM", "LOW", "REJECT"}


def call_api(url, payload, step_name, job_id):
    # LLM endpoints can take up to 90s × 3 retries + overhead.
    # Use a generous but finite timeout so the runner never hangs forever.
    REQUEST_TIMEOUT = 310  # seconds

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.Timeout:
        print(f"[JOB {job_id}] {step_name.upper()} REQUEST TIMEOUT (>{REQUEST_TIMEOUT}s)")
        return None
    except Exception as e:
        print(f"[JOB {job_id}] {step_name.upper()} NETWORK ERROR: {e}")
        return None

    if response.status_code >= 500:
        print(f"[JOB {job_id}] {step_name.upper()} RETRYING (SERVER ERROR {response.status_code})")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.Timeout:
            print(f"[JOB {job_id}] {step_name.upper()} RETRY TIMEOUT")
            return None
        except Exception as e:
            print(f"[JOB {job_id}] {step_name.upper()} RETRY FAILED: {e}")
            return None

    return response

jobs = [
    {
        "title": "Data Analyst",
        "company": "YipitData",
        "location": "India",
        "type": "remote",
        "job_description": "Analyze large alternative datasets, validate data quality, derive business insights, and support research workflows for clients using SQL, Excel, and analytical reasoning. Suitable for candidates with strong analytical skills and early data experience.",
        "source": "https://in.indeed.com/q-entry-level-remote-data-analyst-python-jobs.html",
    },
    {
        "title": "Data QA Associate",
        "company": "YipitData",
        "location": "India",
        "type": "remote",
        "job_description": "Support merchant and vendor data quality operations, investigate anomalies, validate datasets, and maintain reliable data outputs. Good fit for 0-2 years of experience in data analysis, QA, Excel, SQL, or Python-based data checks.",
        "source": "https://in.indeed.com/q-entry-level-remote-data-analyst-python-jobs.html",
    },
    {
        "title": "Data Quality Analyst II",
        "company": "HighLevel",
        "location": "India",
        "type": "remote",
        "job_description": "Work with revenue operations and data teams to improve CRM and business data quality, identify inconsistencies, run validation checks, and support data-driven decisions across an AI-powered SaaS platform.",
        "source": "https://jobs.lever.co/gohighlevel/6fea3b2b-233f-48af-bc36-48162486d6d7",
    },
    {
        "title": "Backend Engineer",
        "company": "Soulside AI",
        "location": "India",
        "type": "remote",
        "job_description": "Build backend systems for an AI healthcare platform focused on reducing clinical documentation time. Responsibilities include API development, infrastructure work, product engineering, and collaboration with AI-driven workflow teams.",
        "source": "https://jobs.ashbyhq.com/Soulside%20AI/041401b5-bd04-4c78-aff4-4b713c3627ae",
    },
    {
        "title": "Backend Engineer",
        "company": "SupplyHouse.com",
        "location": "India",
        "type": "remote",
        "job_description": "Develop backend and full-stack features for an e-commerce platform, improve internal systems, build scalable services, and collaborate with product and engineering teams on customer-facing and operational tools.",
        "source": "https://boards.greenhouse.io/embed/job_app?for=supplyhouse&token=5610954004",
    },
    {
        "title": "Applied AI Engineer",
        "company": "Smart Working Solutions",
        "location": "India",
        "type": "remote",
        "job_description": "Design and implement AI solutions for document understanding, report generation, RAG pipelines, and API integrations. Work with unstructured data such as PDFs, documents, and images while collaborating with backend teams.",
        "source": "https://jobs.lever.co/smart-working-solutions/dce90bec-b02f-4210-8f7a-43cc0f9367c6",
    },
    {
        "title": "AI Engineer - Forward Deployed Engineer",
        "company": "Deductive AI",
        "location": "India",
        "type": "remote",
        "job_description": "Work with customers to adapt and deploy AI SRE agents for production incident response. Responsibilities include customer discovery, platform configuration, AI workflow integration, and technical problem solving.",
        "source": "https://jobs.ashbyhq.com/deductive/124b540e-f84f-46d5-9752-f151361b8223",
    },
    {
        "title": "Data Analyst - Fresher",
        "company": "PharmaForceIQ",
        "location": "India",
        "type": "remote",
        "job_description": "Support healthcare and life-sciences marketing analytics by cleaning data, preparing reports, tracking engagement metrics, and helping teams make data-driven decisions. Suitable for freshers with Excel, SQL, and analytical skills.",
        "source": "https://internshala.com/job/detail/fresher-remote-data-analyst-job-at-pharmaforceiq1774485014",
    },
    {
        "title": "Data Analyst",
        "company": "Gullak",
        "location": "Bangalore, India",
        "type": "on-site",
        "job_description": "Join the growth team to analyze product and business data, build repeatable analyses, identify automation opportunities, and present insights to product, growth, and business stakeholders. Suitable for 0-2 years of experience.",
        "source": "https://internshala.com/job/detail/fresher-remote-data-analyst-job-at-gullak--gold-savings-simplified1771029494",
    },
    {
        "title": "Data Analyst",
        "company": "Daice Labs",
        "location": "India",
        "type": "remote",
        "job_description": "Analyze datasets for an AI research and product company, create data models, perform statistical analysis, and deliver insights that support governed AI systems and decision-making workflows.",
        "source": "https://internshala.com/job/detail/fresher-remote-data-analyst-job-at-daice-labs1771979592",
    },
    {
        "title": "Junior Data Analyst",
        "company": "Trivora Systems",
        "location": "India",
        "type": "remote",
        "job_description": "Perform data analysis using Excel, Python, and SQL, identify trends and anomalies, build reports, and support data-driven decision-making. Designed for freshers or early-career analysts.",
        "source": "https://internshala.com/job/detail/fresher-remote-junior-data-analyst-job-at-trivora-systems1771411749",
    },
    {
        "title": "Data Analyst",
        "company": "Binated",
        "location": "Pune, India",
        "type": "on-site",
        "job_description": "Collect, clean, and analyze data from multiple sources, write SQL queries, develop dashboards, validate reporting accuracy, and present actionable insights to business teams. Freshers with strong skills may apply.",
        "source": "https://internshala.com/job/detail/fresher-remote-data-analyst-job-at-binated1773138068",
    },
]

input_jobs = sys.argv[1:]

if input_jobs:
    jobs = [{"title": "CLI Job", "company": "", "job_description": input_jobs[0]}]
else:
    # Batch loop disabled — run only the first job to avoid excessive DB calls.
    # Re-enable by removing the slice below once execution issues are resolved.
    jobs = jobs[:1]

success_count = 0
results = []          # tracking: one entry per job processed

for i, job in enumerate(jobs, 1):
    job_description = f"{job['title']} at {job['company']}\n\n{job['job_description']}"

    # Tracking record — filled in as the job progresses
    record = {
        "job_id":         i,
        "title":          job.get("title", ""),
        "company":        job.get("company", ""),
        "score":          None,
        "decision":       None,
        "application_id": None,
        "status":         "failed",
        "failed_at":      None,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }

    print(f"\n[JOB {i}] START")

    # ------------------------------------------------------------------
    # MATCH
    # ------------------------------------------------------------------
    print(f"[JOB {i}] match")
    match_response = call_api(
        f"{BASE_URL}/match",
        {"job_description": job_description},
        "match",
        i,
    )
    if match_response is None or match_response.status_code != 200:
        print(f"[JOB {i}] FAILED at match")
        if match_response is not None:
            print(match_response.text)
        record["failed_at"] = "match"
        results.append(record)
        continue
    try:
        match_data = match_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at match")
        print(match_response.text)
        print(f"[JOB {i}] FAILED at match")
        record["failed_at"] = "match"
        results.append(record)
        continue

    score    = match_data.get("match_score", 0.0)
    decision = match_data.get("decision", "REJECT")
    if decision not in VALID_DECISIONS:
        decision = "REJECT"

    record["score"]    = score
    record["decision"] = decision

    if decision == "HIGH":
        print(f"[JOB {i}] HIGH MATCH (score={score}) — running full pipeline")
    elif decision == "MEDIUM":
        print(f"[JOB {i}] MEDIUM MATCH (score={score}) — running partial pipeline")
    elif decision == "LOW":
        print(f"[JOB {i}] LOW MATCH (score={score}) — minimal processing, logging only")
        print(match_data)
        record["status"] = "logged"
        results.append(record)
        continue
    else:
        print(f"[JOB {i}] REJECT (score={score}) — skipping")
        record["status"] = "rejected"
        results.append(record)
        continue

    # ------------------------------------------------------------------
    # TAILOR  (HIGH + MEDIUM)
    # ------------------------------------------------------------------
    print(f"[JOB {i}] tailor")
    tailor_response = call_api(
        f"{BASE_URL}/tailor",
        {"job_description": job_description},
        "tailor",
        i,
    )
    if tailor_response is None or tailor_response.status_code != 200:
        print(f"[JOB {i}] FAILED at tailor")
        if tailor_response is not None:
            print(tailor_response.text)
        record["failed_at"] = "tailor"
        results.append(record)
        continue
    try:
        tailor_data = tailor_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at tailor")
        print(tailor_response.text)
        print(f"[JOB {i}] FAILED at tailor")
        record["failed_at"] = "tailor"
        results.append(record)
        continue
    print(f"[JOB {i}] TAILOR SUCCESS")
    print(tailor_data)

    # ------------------------------------------------------------------
    # COVER LETTER  (HIGH required — MEDIUM optional)
    # ------------------------------------------------------------------
    # cover_letter_text holds the plain string extracted from the response,
    # or None if the step was skipped / failed on a MEDIUM decision.
    cover_letter_text = None
    if decision in ("HIGH", "MEDIUM"):
        print(f"[JOB {i}] cover-letter")
        cover_letter_response = call_api(
            f"{BASE_URL}/cover-letter",
            {"job_description": job_description},
            "cover-letter",
            i,
        )
        if cover_letter_response is None or cover_letter_response.status_code != 200:
            print(f"[JOB {i}] FAILED at cover-letter")
            if cover_letter_response is not None:
                print(cover_letter_response.text)
            if decision == "HIGH":
                record["failed_at"] = "cover-letter"
                results.append(record)
                continue
            print(f"[JOB {i}] MEDIUM — continuing without cover letter")
        else:
            try:
                cover_letter_resp_data = cover_letter_response.json()
                # Extract the plain string from {"cover_letter": "..."}
                cover_letter_text = cover_letter_resp_data.get("cover_letter") or None
                print(f"[JOB {i}] COVER-LETTER SUCCESS")
                print(cover_letter_text)
            except Exception:
                print(f"[JOB {i}] INVALID JSON at cover-letter")
                print(cover_letter_response.text)
                if decision == "HIGH":
                    print(f"[JOB {i}] FAILED at cover-letter")
                    record["failed_at"] = "cover-letter"
                    results.append(record)
                    continue
                print(f"[JOB {i}] MEDIUM — continuing without cover letter")

    # ------------------------------------------------------------------
    # APPLICATION  (HIGH + MEDIUM)
    #
    # Required fields:  job_title, company, job_description
    # Optional fields:  match_score, resume_version, cover_letter
    #
    # match_score   — float extracted from match response
    # resume_version — fixed tag "auto_v1" (no full resume text sent)
    # cover_letter  — plain string extracted from cover-letter response
    # ------------------------------------------------------------------
    job_title = job.get("title") or "Unknown"
    company   = job.get("company") or "Unknown"

    applications_payload = {
        "job_title":       job_title,
        "company":         company,
        "job_description": job_description,
        "match_score":     score,
        "resume_version":  "auto_v1",
        "cover_letter":    cover_letter_text,
    }

    print(f"[JOB {i}] applications — payload:")
    print(json.dumps(applications_payload, indent=2))

    applications_response = call_api(
        f"{BASE_URL}/applications/",
        applications_payload,
        "applications",
        i,
    )
    if applications_response is None or applications_response.status_code != 200:
        print(f"[JOB {i}] FAILED at applications (HTTP {getattr(applications_response, 'status_code', 'N/A')})")
        if applications_response is not None:
            print(applications_response.text)
        record["failed_at"] = "applications"
        results.append(record)
        continue
    try:
        applications_data = applications_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at applications")
        print(applications_response.text)
        print(f"[JOB {i}] FAILED at applications")
        record["failed_at"] = "applications"
        results.append(record)
        continue

    print(f"[JOB {i}] APPLICATIONS SUCCESS — response:")
    print(json.dumps(applications_data, indent=2))
    record["application_id"] = applications_data.get("id")
    record["status"] = "success"
    results.append(record)
    success_count += 1
    print(f"[JOB {i}] COMPLETED SUCCESSFULLY")

print(f"\nTOTAL SUCCESS: {success_count}/{len(jobs)}")

# ------------------------------------------------------------------
# Metrics summary
# ------------------------------------------------------------------
decision_counts = Counter(r["decision"] or "unknown" for r in results)
status_counts   = Counter(r["status"] for r in results)

print("\n--- Run Summary ---")
print(f"Decision Distribution : {dict(decision_counts)}")
print(f"Status Distribution   : {dict(status_counts)}")
print(f"Total processed       : {len(results)}")

# ------------------------------------------------------------------
# Persist results to file
# ------------------------------------------------------------------
output_path = Path(__file__).resolve().parent.parent / "run_results.json"
with open(output_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"Results saved to      : {output_path}")
