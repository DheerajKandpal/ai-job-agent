from pydantic import BaseModel


class CoverLetterRequest(BaseModel):
    job_description: str


class CoverLetterResponse(BaseModel):
    cover_letter: str
