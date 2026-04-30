"""
endpoint_sender.py — Submits job applications to external endpoints via HTTP POST.
"""

import requests


def send_to_endpoint(job: dict, payload: dict) -> None:
    """
    POST a job application to the URL specified in job["apply_endpoint"].

    Args:
        job:     Job dict — must contain 'apply_endpoint' (str URL).
        payload: Application payload — must contain 'resume_text' and 'cover_letter'.

    Raises:
        requests.exceptions.Timeout:      If the request exceeds 10 seconds.
        requests.exceptions.RequestException: On any network-level failure.
        Exception: If the server returns a non-2xx status code.
    """
    url: str = job["apply_endpoint"]

    print(f"Sending application to endpoint: {url}")

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "resume": payload["resume_text"],
            "cover_letter": payload["cover_letter"],
        },
        timeout=10,
    )

    if not (200 <= response.status_code <= 299):
        raise Exception(
            f"Endpoint returned non-2xx status {response.status_code}: {response.text}"
        )

    print("Endpoint application successful")
