import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationException
from app.core.security import decode_access_token
from app.core.storage.base import StorageAdapter
from app.core.storage.local import LocalStorageAdapter
from app.models.user import User
from app.models.workspace import Workspace
from app.services.auth_service import AuthService
from app.services.workspace_service import WorkspaceService

security_bearer = HTTPBearer(auto_error=False)


def get_storage_adapter() -> StorageAdapter:
    """Dependency provider for storage adapter."""
    return LocalStorageAdapter()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Authenticate request using Bearer JWT token."""
    if not credentials or not credentials.credentials:
        raise AuthenticationException(
            "Authentication required. Please provide a valid Bearer token."
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    jti = payload.get("jti")
    if not jti or AuthService.is_token_revoked(db, jti):
        raise AuthenticationException("Token has been revoked or is invalid.")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationException("Invalid token credentials.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise AuthenticationException("Invalid token subject format.") from exc

    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    if not user:
        raise AuthenticationException("User account does not exist.")

    if not user.is_active:
        raise AuthenticationException("User account is inactive.")

    return user


def get_current_workspace_context(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[Workspace, str]:
    """Verify user has membership access to the requested workspace."""
    return WorkspaceService.get_workspace_for_user(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
