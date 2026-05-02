from app.core.config import settings
from app.core.cache import get as cache_get
from app.core.cache import set as cache_set
from app.core.logging import get_logger
from app.services.matcher.matcher import match_resume_to_job as match
from app.services.tracker.db_service import get_resume_by_version as get_resume

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Decision thresholds
# ---------------------------------------------------------------------------
HIGH_THRESHOLD   = 0.70
MEDIUM_THRESHOLD = 0.35
LOW_THRESHOLD    = 0.22


def classify_match(score: float) -> str:
    """Convert a numeric match score into a decision tier."""
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    elif score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    elif score >= LOW_THRESHOLD:
        return "LOW"
    else:
        return "REJECT"


def process_match(job_description: str) -> dict:
    # Strip whitespace and non-printable characters (mirrors route-layer validation)
    cleaned = "".join(c for c in (job_description or "").strip() if c.isprintable()).strip()
    if not cleaned:
        raise ValueError("job_description cannot be empty")

    resume = cache_get("resume")
    if resume is None:
        logger.info("db call start: get_resume")
        resume = get_resume(settings.RESUME_VERSION)
        logger.info("db call end: get_resume")
        if resume is not None:
            cache_set("resume", resume, ttl=300)
    if resume is None:
        raise ValueError("resume not found")

    logger.info("match call start")
    result = match(resume, job_description)
    logger.info("match call end")

    score    = float(result.get("match_score", 0.0))
    decision = classify_match(score)

    logger.info(f"[MATCH] score={score}, decision={decision}")

    return {
        "match_score":    score,
        "matched_skills": list(result.get("matched_skills", [])),
        "decision":       decision,
    }
