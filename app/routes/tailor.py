from fastapi import APIRouter

from app.core.logging import get_logger
from app.schemas.tailor import TailorRequest, TailorResponse, TailoredResume
from app.services.tailor_service import process_tailor

router = APIRouter()
logger = get_logger(__name__)


@router.post("/tailor", response_model=TailorResponse)
def tailor_resume(request: TailorRequest) -> TailorResponse:
    logger.info("request received: tailor")
    result = process_tailor(request.job_description)
    logger.info("response status: 200")
    return TailorResponse(
        tailored_resume=TailoredResume(**result["tailored_resume"])
    )
