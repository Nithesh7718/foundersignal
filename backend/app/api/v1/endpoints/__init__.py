from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.workspaces import router as workspaces_router

__all__ = [
    "auth_router",
    "conversations_router",
    "health_router",
    "workspaces_router",
]
