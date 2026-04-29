from fastapi import APIRouter, HTTPException

from app.schemas.tailor import TailorRequest, TailorResponse, TailoredResume
from app.services.tailor_service import process_tailor

router = APIRouter()


@router.post("/tailor", response_model=TailorResponse)
def tailor_resume(request: TailorRequest) -> TailorResponse:
    try:
        result = process_tailor(request.job_description)
        return TailorResponse(
            tailored_resume=TailoredResume(**result["tailored_resume"])
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
