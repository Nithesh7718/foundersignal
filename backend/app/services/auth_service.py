import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationException, ConflictException
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import RevokedToken, User
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.user import UserCreate


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return re.sub(r"^-+|-+$", "", text) or "workspace"


class AuthService:
    @staticmethod
    def register_user(db: Session, user_in: UserCreate) -> tuple[User, Workspace, str]:
        # Check if email is already registered
        existing = db.execute(
            select(User).where(User.email == user_in.email.lower().strip())
        ).scalar_one_or_none()
        if existing:
            raise ConflictException("A user with this email address already exists.")

        hashed_pw = get_password_hash(user_in.password)
        user = User(
            email=user_in.email.lower().strip(),
            hashed_password=hashed_pw,
            full_name=user_in.full_name.strip(),
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Create default personal workspace
        clean_name = user.full_name.strip()
        slug_base = slugify(clean_name)
        unique_slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"

        workspace = Workspace(
            name=f"{clean_name}'s Workspace",
            slug=unique_slug,
            owner_id=user.id,
        )
        db.add(workspace)
        db.flush()

        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
        db.add(membership)
        db.commit()
        db.refresh(user)
        db.refresh(workspace)

        token, _jti, _exp = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "name": user.full_name},
        )
        return user, workspace, token

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> tuple[User, str]:
        user = db.execute(
            select(User).where(User.email == email.lower().strip())
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationException("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationException("User account is inactive.")

        token, _jti, _exp = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "name": user.full_name},
        )
        return user, token

    @staticmethod
    def logout_user(db: Session, token: str) -> None:
        payload = decode_access_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return

        expires_at = datetime.fromtimestamp(exp, tz=UTC)
        revoked = RevokedToken(jti=jti, expires_at=expires_at)
        db.add(revoked)
        db.commit()

    @staticmethod
    def is_token_revoked(db: Session, jti: str) -> bool:
        revoked = db.execute(
            select(RevokedToken).where(RevokedToken.jti == jti)
        ).scalar_one_or_none()
        return revoked is not None
