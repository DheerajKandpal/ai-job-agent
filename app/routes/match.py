from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.schemas.match import MatchRequest, MatchResponse
from app.services.match_service import process_match
from app.utils.security import sanitize_prompt, validate_job_description

router = APIRouter()


@router.post("/match", response_model=MatchResponse)
def match_job(request: MatchRequest) -> MatchResponse:
    try:
        validated_text = validate_job_description(request.job_description)
        clean_text = sanitize_prompt(validated_text)
        result = process_match(clean_text)
        return MatchResponse(**result)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
