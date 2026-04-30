from fastapi import APIRouter

from app.core.logging import get_logger
from app.schemas.cover_letter import CoverLetterRequest, CoverLetterResponse
from app.services.cover_letter_service import process_cover_letter

router = APIRouter()
logger = get_logger(__name__)


@router.post("/cover-letter", response_model=CoverLetterResponse)
def generate_cover_letter(request: CoverLetterRequest) -> CoverLetterResponse:
    logger.info("request received: cover_letter")
    result = process_cover_letter(request.job_description)
    logger.info("response status: 200")
    return CoverLetterResponse(**result)
