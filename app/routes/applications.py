from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.tracker.db_service import (
    get_all_applications,
    get_application_by_id,
    save_application,
    update_status,
)

router = APIRouter(prefix="/applications")


class ApplyRequest(BaseModel):
    job_title: str
    company: str
    job_description: str
    match_score: Optional[float] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None


class ApplyResponse(BaseModel):
    message: str
    id: int


class ApplicationListItem(BaseModel):
    id: int
    job_title: str
    company: str
    status: str
    created_at: datetime


class ApplicationDetail(BaseModel):
    id: int
    job_title: str
    company: str
    job_description: str
    match_score: Optional[float] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None
    status: str
    created_at: datetime


class UpdateStatusRequest(BaseModel):
    status: Literal["applied", "interview", "rejected"]


class MessageResponse(BaseModel):
    message: str


@router.post("/", response_model=ApplyResponse)
def apply(payload: ApplyRequest) -> ApplyResponse:
    try:
        application_id = save_application(payload.model_dump(exclude_none=True))
        return ApplyResponse(message="Application saved", id=application_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/", response_model=List[ApplicationListItem])
def list_applications(limit: int = 10, offset: int = 0) -> List[ApplicationListItem]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be greater than 0")
    if limit > 100:
        raise HTTPException(status_code=400, detail="limit must be less than or equal to 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")

    try:
        rows = get_all_applications(limit=limit, offset=offset)
        return [
            ApplicationListItem(
                id=row["id"],
                job_title=row["job_title"],
                company=row["company"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{id}", response_model=ApplicationDetail)
def get_application(id: int) -> ApplicationDetail:
    if id <= 0:
        raise HTTPException(status_code=400, detail="id must be greater than 0")

    try:
        row = get_application_by_id(id)
        return ApplicationDetail(**row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/{id}", response_model=MessageResponse)
def patch_application_status(id: int, payload: UpdateStatusRequest) -> MessageResponse:
    if id <= 0:
        raise HTTPException(status_code=400, detail="id must be greater than 0")

    try:
        update_status(id, payload.status)
        return MessageResponse(message="Status updated")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
