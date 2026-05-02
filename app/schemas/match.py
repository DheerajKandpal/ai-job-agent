from typing import List, Literal

from pydantic import BaseModel


class MatchRequest(BaseModel):
    job_description: str


class MatchResponse(BaseModel):
    match_score: float
    matched_skills: List[str]
    decision: Literal["HIGH", "MEDIUM", "LOW", "REJECT"]
