from fastapi import APIRouter

from app.api.v1.assessments import exams_router, flashcards_router, jobs_router, progress_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.documents import router as documents_router
from app.api.v1.orgs import router as orgs_router
from app.api.v1.support import router as support_router
from app.api.v1.team import router as team_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(orgs_router)
api_router.include_router(billing_router)
api_router.include_router(team_router)
api_router.include_router(documents_router)
api_router.include_router(exams_router)
api_router.include_router(flashcards_router)
api_router.include_router(jobs_router)
api_router.include_router(progress_router)
api_router.include_router(support_router)
