"""
email_sender.py — Sends job application emails via SMTP.

Uses Python standard library only (smtplib + email.message).
Configuration is read entirely from environment variables.
"""

import os
import smtplib
from email.message import EmailMessage


def _get_smtp_config() -> tuple[str, int, str, str]:
    """
    Read and validate SMTP configuration from environment variables.

    Returns:
        Tuple of (host, port, user, password).

    Raises:
        ValueError: If any required environment variable is missing or empty.
    """
    host = os.getenv("EMAIL_HOST")
    port_str = os.getenv("EMAIL_PORT")
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    missing = [
        name
        for name, value in [
            ("EMAIL_HOST", host),
            ("EMAIL_PORT", port_str),
            ("EMAIL_USER", user),
            ("EMAIL_PASS", password),
        ]
        if not value
    ]
    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    try:
        port = int(port_str)  # type: ignore[arg-type]
    except ValueError:
        raise ValueError(f"EMAIL_PORT must be an integer, got: {port_str!r}")

    return host, port, user, password  # type: ignore[return-value]


def send_email(job: dict, payload: dict) -> None:
    """
    Send a job application email via SMTP.

    Reads SMTP credentials from environment variables:
        EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS

    Args:
        job:     Job dict — must contain 'apply_email' and 'title'.
        payload: Application payload — must contain 'cover_letter' and 'resume_text'.

    Raises:
        ValueError: If any required environment variable is missing.
        smtplib.SMTPException: On any SMTP-level failure.
        Exception: Any other unexpected error is re-raised for the caller to handle.
    """
    host, port, user, password = _get_smtp_config()

    recipient: str = job["apply_email"]
    subject: str = f"Job Application – {job['title']}"
    body: str = payload["cover_letter"]
    resume_text: str = payload["resume_text"]

    # Build the message
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach resume as plain-text file
    msg.add_attachment(
        resume_text.encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename="resume.txt",
    )

    print(f"Sending email to {recipient}")

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    print("Email sent successfully")
