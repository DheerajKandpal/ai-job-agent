from fastapi import APIRouter, HTTPException

from app.schemas.match import MatchRequest, MatchResponse
from app.services.match_service import process_match

router = APIRouter()


@router.post("/match", response_model=MatchResponse)
def match_job(request: MatchRequest) -> MatchResponse:
    try:
        result = process_match(request.job_description)
        return MatchResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
