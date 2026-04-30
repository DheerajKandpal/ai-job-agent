from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.tracker.db_service import (
    get_all_applications,
    get_application_by_id,
    save_application,
    update_status,
)

router = APIRouter(prefix="/applications")
logger = get_logger(__name__)


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
    logger.info("request received: applications.apply")
    application_id = save_application(payload.model_dump(exclude_none=True))
    logger.info("response status: 200")
    return ApplyResponse(message="Application saved", id=application_id)


@router.get("/", response_model=List[ApplicationListItem])
def list_applications(limit: int = 10, offset: int = 0) -> List[ApplicationListItem]:
    logger.info("request received: applications.list")
    if limit <= 0:
        logger.error("request failed: applications.list (invalid limit)")
        raise HTTPException(status_code=400, detail="limit must be greater than 0")
    if limit > 100:
        logger.error("request failed: applications.list (limit too large)")
        raise HTTPException(status_code=400, detail="limit must be less than or equal to 100")
    if offset < 0:
        logger.error("request failed: applications.list (invalid offset)")
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")

    rows = get_all_applications(limit=limit, offset=offset)
    logger.info("response status: 200")
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


@router.get("/{id}", response_model=ApplicationDetail)
def get_application(id: int) -> ApplicationDetail:
    logger.info("request received: applications.get")
    if id <= 0:
        logger.error("request failed: applications.get (invalid id)")
        raise HTTPException(status_code=400, detail="id must be greater than 0")

    row = get_application_by_id(id)
    logger.info("response status: 200")
    return ApplicationDetail(**row)


@router.patch("/{id}", response_model=MessageResponse)
def patch_application_status(id: int, payload: UpdateStatusRequest) -> MessageResponse:
    logger.info("request received: applications.patch_status")
    if id <= 0:
        logger.error("request failed: applications.patch_status (invalid id)")
        raise HTTPException(status_code=400, detail="id must be greater than 0")

    update_status(id, payload.status)
    logger.info("response status: 200")
    return MessageResponse(message="Status updated")
