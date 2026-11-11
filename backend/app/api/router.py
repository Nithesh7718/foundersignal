from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.transcription_jobs import router as transcription_jobs_router
from app.api.v1.endpoints.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["Workspaces"])
api_router.include_router(conversations_router, tags=["Conversations"])
api_router.include_router(transcription_jobs_router, tags=["Transcription Jobs"])
