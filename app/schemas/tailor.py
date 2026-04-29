from typing import List

from pydantic import BaseModel


class TailorRequest(BaseModel):
    job_description: str


class TailoredResume(BaseModel):
    summary: str
    experience: List[str]
    skills: List[str]


class TailorResponse(BaseModel):
    tailored_resume: TailoredResume
