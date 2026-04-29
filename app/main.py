from fastapi import FastAPI

from app.routes.applications import router as applications_router
from app.routes.cover_letter import router as cover_letter_router
from app.routes.match import router as match_router
from app.routes.tailor import router as tailor_router

app = FastAPI()

app.include_router(match_router)
app.include_router(tailor_router)
app.include_router(cover_letter_router)
app.include_router(applications_router)


@app.get("/")
def root():
    return {"status": "ok"}
