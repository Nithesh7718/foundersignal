from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, security_bearer
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Register a new user account and initialize personal workspace."""
    user, _workspace, access_token = AuthService.register_user(db, user_in)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLogin,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate with email and password to receive an access token."""
    user, access_token = AuthService.authenticate_user(
        db,
        email=credentials.email,
        password=credentials.password,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Retrieve details for the currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Revoke the current access token."""
    if credentials and credentials.credentials:
        AuthService.logout_user(db, credentials.credentials)
    return {"message": "Successfully logged out."}
