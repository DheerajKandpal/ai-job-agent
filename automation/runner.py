import os
import requests
import sys


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("Missing API_KEY")
    exit()

headers = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json",
}

THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.5))


def call_api(url, payload, step_name, job_id):
    try:
        response = requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"[JOB {job_id}] {step_name.upper()} NETWORK ERROR: {e}")
        return None

    if response.status_code >= 500:
        print(f"[JOB {job_id}] {step_name.upper()} RETRYING (SERVER ERROR)")
        try:
            response = requests.post(url, headers=headers, json=payload)
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

success_count = 0

for i, job in enumerate(jobs, 1):
    job_description = f"{job['title']} at {job['company']}\n\n{job['job_description']}"

    print(f"\n[JOB {i}] START")

    print(f"[JOB {i}] match")
    match_response = call_api(
        f"{BASE_URL}/match",
        {"job_description": job_description},  # adjust if needed
        "match",
        i,
    )
    if match_response is None or match_response.status_code != 200:
        print(f"[JOB {i}] FAILED at match")
        if match_response is not None:
            print(match_response.text)
        continue
    try:
        match_data = match_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at match")
        print(match_response.text)
        print(f"[JOB {i}] FAILED at match")
        continue
    score = match_data.get("score", 0)
    if score < THRESHOLD:
        print(f"[JOB {i}] SKIPPED (low match: {score})")
        continue
    print(f"[JOB {i}] MATCH SUCCESS")
    print(match_data)

    print(f"[JOB {i}] tailor")
    tailor_response = call_api(
        f"{BASE_URL}/tailor",
        {
            "job_description": job_description,  # adjust if needed
            "resume": "your_resume_text",  # adjust if needed
            "match": match_data,  # adjust if needed
        },
        "tailor",
        i,
    )
    if tailor_response is None or tailor_response.status_code != 200:
        print(f"[JOB {i}] FAILED at tailor")
        if tailor_response is not None:
            print(tailor_response.text)
        continue
    try:
        tailor_data = tailor_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at tailor")
        print(tailor_response.text)
        print(f"[JOB {i}] FAILED at tailor")
        continue
    print(f"[JOB {i}] TAILOR SUCCESS")
    print(tailor_data)

    print(f"[JOB {i}] cover-letter")
    cover_letter_response = call_api(
        f"{BASE_URL}/cover-letter",
        {
            "job_description": job_description,  # adjust if needed
            "resume": "your_resume_text",  # adjust if needed
            "tailored_resume": tailor_data,  # adjust if needed
        },
        "cover-letter",
        i,
    )
    if cover_letter_response is None or cover_letter_response.status_code != 200:
        print(f"[JOB {i}] FAILED at cover-letter")
        if cover_letter_response is not None:
            print(cover_letter_response.text)
        continue
    try:
        cover_letter_data = cover_letter_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at cover-letter")
        print(cover_letter_response.text)
        print(f"[JOB {i}] FAILED at cover-letter")
        continue
    print(f"[JOB {i}] COVER-LETTER SUCCESS")
    print(cover_letter_data)

    print(f"[JOB {i}] applications")
    applications_response = call_api(
        f"{BASE_URL}/applications/",
        {
            "job_description": job_description,  # adjust if needed
            "match": match_data,  # adjust if needed
            "tailored_resume": tailor_data,  # adjust if needed
            "cover_letter": cover_letter_data,  # adjust if needed
        },
        "applications",
        i,
    )
    if applications_response is None or applications_response.status_code != 200:
        print(f"[JOB {i}] FAILED at applications")
        if applications_response is not None:
            print(applications_response.text)
        continue
    try:
        applications_data = applications_response.json()
    except Exception:
        print(f"[JOB {i}] INVALID JSON at applications")
        print(applications_response.text)
        print(f"[JOB {i}] FAILED at applications")
        continue
    print(f"[JOB {i}] APPLICATIONS SUCCESS")
    print(applications_data)
    success_count += 1
    print(f"[JOB {i}] COMPLETED SUCCESSFULLY")

print(f"\nTOTAL SUCCESS: {success_count}/{len(jobs)}")
