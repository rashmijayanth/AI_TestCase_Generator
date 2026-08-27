from datetime import timedelta

import jwt
import pytest

from testgen.platform.config import Settings
from testgen.platform.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.unit
def test_hash_password_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


@pytest.mark.unit
def test_create_and_decode_access_token_round_trip() -> None:
    settings = Settings(jwt_secret_key="test-secret-at-least-32-bytes-long")

    token = create_access_token(subject="user-1", organization_id="org-1", settings=settings)
    payload = decode_access_token(token, settings=settings)

    assert payload["sub"] == "user-1"
    assert payload["org"] == "org-1"


@pytest.mark.unit
def test_decode_rejects_token_signed_with_a_different_secret() -> None:
    token = create_access_token(
        subject="user-1",
        organization_id="org-1",
        settings=Settings(jwt_secret_key="secret-a-that-is-at-least-32-bytes"),
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(
            token, settings=Settings(jwt_secret_key="secret-b-that-is-at-least-32-bytes")
        )


@pytest.mark.unit
def test_decode_rejects_expired_token() -> None:
    settings = Settings(jwt_secret_key="test-secret-at-least-32-bytes-long")
    token = create_access_token(
        subject="user-1",
        organization_id="org-1",
        settings=settings,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, settings=settings)
