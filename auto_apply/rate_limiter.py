"""
rate_limiter.py — Rate limiting for the autonomous job application pipeline.

Enforces:
  - A per-run job cap (max_jobs_per_run = 20)
  - A random inter-job delay of 30–60 seconds between jobs
"""

import random
import time

MAX_JOBS_PER_RUN: int = 20


def should_continue(processed_count: int) -> bool:
    """
    Return True if the pipeline should process another job.

    Args:
        processed_count: Number of jobs successfully processed so far in this run.

    Returns:
        True  — processed_count is below the per-run cap.
        False — the cap has been reached; the caller should stop.
    """
    return processed_count < MAX_JOBS_PER_RUN


def wait() -> None:
    """
    Sleep for a random duration between 30 and 60 seconds (inclusive).

    Called between jobs to avoid hammering external services.
    """
    delay: int = random.randint(30, 60)
    time.sleep(delay)
