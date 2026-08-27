"""POST /register (bootstraps an organization + its first admin user -- there's
no SSO/invite flow in this portfolio scope, so registration has to be open for
the system to be usable at all) and POST /token (OAuth2 password flow, DESIGN.md §7).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from testgen.api.deps import ADMIN_ROLE_NAME, DbSession
from testgen.api.schemas import RegisterRequest, TokenResponse, UserOut
from testgen.platform.models import Organization, Role, User, UserRole
from testgen.platform.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> UserOut:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    org = Organization(name=payload.organization_name)
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    # Role names are global (Phase 1 schema); the per-org assignment lives on
    # UserRole. Reuse the shared "admin" role row if another org already
    # created it, rather than erroring on the unique-name constraint.
    admin_role = db.execute(select(Role).where(Role.name == ADMIN_ROLE_NAME)).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(name=ADMIN_ROLE_NAME, description="Full administrative access")
        db.add(admin_role)
        db.flush()

    db.add(UserRole(user_id=user.id, role_id=admin_role.id, organization_id=org.id))
    db.commit()

    return UserOut(
        id=str(user.id), email=user.email, full_name=user.full_name, organization_id=str(org.id)
    )


@router.post("/token", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
) -> TokenResponse:
    user = db.execute(select(User).where(User.email == form_data.username)).scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=str(user.id), organization_id=str(user.organization_id))
    return TokenResponse(access_token=token)
