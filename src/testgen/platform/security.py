"""Password hashing (bcrypt) and JWT issuance/verification for the API's
OAuth2-password-flow auth (DESIGN.md §7: "OAuth2/JWT + RBAC").
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from testgen.platform.config import Settings, get_settings

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    *,
    subject: str,
    organization_id: str,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = settings or get_settings()
    expire = datetime.now(UTC) + (expires_delta or timedelta(hours=settings.jwt_expire_hours))
    payload: dict[str, Any] = {"sub": subject, "org": organization_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
