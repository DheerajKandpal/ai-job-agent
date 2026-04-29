from fastapi import APIRouter, HTTPException

from app.schemas.cover_letter import CoverLetterRequest, CoverLetterResponse
from app.services.cover_letter_service import process_cover_letter

router = APIRouter()


@router.post("/cover-letter", response_model=CoverLetterResponse)
def generate_cover_letter(request: CoverLetterRequest) -> CoverLetterResponse:
    try:
        result = process_cover_letter(request.job_description)
        return CoverLetterResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
