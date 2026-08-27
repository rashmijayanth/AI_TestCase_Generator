"""Pydantic request/response models for the API (distinct from
generation/schemas.py, which are LLM structured-output contracts).
"""

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    organization_name: str
    email: str
    full_name: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    organization_id: str


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
