import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

REQUEST_TIMEOUT = 60


@dataclass(frozen=True)
class PipelineConfig:
    backend_url: str
    api_key: str


def load_config() -> PipelineConfig:
    backend_url = (os.getenv("BACKEND_URL") or "").strip()
    api_key = (os.getenv("API_KEY") or "").strip()

    missing: list[str] = []
    if not backend_url:
        missing.append("BACKEND_URL")
    if not api_key:
        missing.append("API_KEY")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return PipelineConfig(backend_url=backend_url.rstrip("/"), api_key=api_key)


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def call_endpoint(
    config: PipelineConfig,
    endpoint: str,
    payload: dict[str, Any],
    step_name: str,
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{config.backend_url}{endpoint}",
            headers=auth_headers(config.api_key),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"{step_name} failed: network error ({exc})") from exc

    if response.status_code in {401, 403}:
        raise RuntimeError(f"{step_name} failed: authentication error ({response.status_code})")
    if response.status_code >= 500:
        raise RuntimeError(f"{step_name} failed: server error ({response.status_code})")
    if not response.ok:
        body = response.text.strip()
        raise RuntimeError(f"{step_name} failed: HTTP {response.status_code} {body}")

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{step_name} failed: invalid JSON response") from exc


def load_job_description(cli_text: str | None, file_path: str | None) -> str:
    if cli_text:
        return cli_text.strip()
    if file_path:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()

    # Mock input fallback for scheduled runs
    return (
        "Backend Reliability Engineer role. Build resilient APIs, improve observability, "
        "support incident response, optimize PostgreSQL queries, and automate operational workflows."
    )


def run_pipeline(job_description: str, job_title: str, company: str) -> None:
    if len(job_description.strip()) < 20:
        raise RuntimeError("job description is too short")

    config = load_config()

    print("Running match...")
    match_result = call_endpoint(
        config,
        "/match",
        {"job_description": job_description},
        "match",
    )

    print("Tailoring resume...")
    tailor_result = call_endpoint(
        config,
        "/tailor",
        {"job_description": job_description},
        "tailor",
    )

    print("Generating cover letter...")
    cover_letter_result = call_endpoint(
        config,
        "/cover-letter",
        {"job_description": job_description},
        "cover-letter",
    )

    print("Storing application in DB...")
    payload = {
        "job_title": job_title,
        "company": company,
        "job_description": job_description,
        "match_score": match_result.get("match_score"),
        "resume_version": "base_v2",
        "cover_letter": cover_letter_result.get("cover_letter", ""),
    }
    save_result = call_endpoint(config, "/applications/", payload, "applications")

    application_id = save_result.get("id")
    print(f"Pipeline completed successfully. Application ID: {application_id}")
    if tailor_result.get("tailored_resume"):
        print("Tailored resume generated successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI job pipeline without UI.")
    parser.add_argument(
        "--job-description",
        dest="job_description",
        help="Raw job description text.",
    )
    parser.add_argument(
        "--job-description-file",
        dest="job_description_file",
        help="Path to a file containing job description text.",
    )
    parser.add_argument(
        "--job-title",
        default="Automated Job",
        help="Job title to store in DB.",
    )
    parser.add_argument(
        "--company",
        default="Automated Source",
        help="Company name to store in DB.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.job_description and args.job_description_file:
        print("Error: use either --job-description or --job-description-file, not both.")
        return 1

    try:
        job_description = load_job_description(args.job_description, args.job_description_file)
        run_pipeline(job_description, args.job_title.strip(), args.company.strip())
        return 0
    except Exception as exc:
        print(f"Pipeline stopped: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
