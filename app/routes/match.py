from fastapi import APIRouter

from app.core.logging import get_logger
from app.schemas.match import MatchRequest, MatchResponse
from app.services.match_service import process_match
from app.utils.security import sanitize_prompt, validate_job_description

router = APIRouter()
logger = get_logger(__name__)


@router.post("/match", response_model=MatchResponse)
def match_job(request: MatchRequest) -> MatchResponse:
    logger.info("request received: match")
    validated_text = validate_job_description(request.job_description)
    clean_text = sanitize_prompt(validated_text)
    result = process_match(clean_text)
    logger.info("response status: 200")
    return MatchResponse(**result)
