"""FastAPI dependency providers: DB session, current user (JWT), RBAC."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from testgen.platform.db.session import get_db
from testgen.platform.models import Role, User, UserRole
from testgen.platform.security import decode_access_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# The only role this portfolio-scope system actually assigns (register()
# grants it to an org's first user) -- a fuller system would let admins invite
# others and assign narrower roles (e.g. "qa_reviewer"); not built here.
ADMIN_ROLE_NAME = "admin"

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(_oauth2_scheme)], db: DbSession) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise credentials_error from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*role_names: str) -> Callable[[User, Session], User]:
    """Returns a checker function for the caller to wrap in Depends(...) at the
    route definition -- e.g. `user: Annotated[User, Depends(require_roles("admin"))]`.
    Returning the plain function (not Depends(...) itself) keeps this cleanly
    typed: FastAPI's own Depends() is what resolves to the User type at the use
    site, not this factory.
    """

    def _check(user: CurrentUser, db: DbSession) -> User:
        held_roles = set(
            db.execute(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == user.id, UserRole.organization_id == user.organization_id
                )
            )
            .scalars()
            .all()
        )
        if not held_roles.intersection(role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(role_names)}",
            )
        return user

    return _check
