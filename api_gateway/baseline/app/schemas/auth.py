from typing import Literal

from pydantic import BaseModel, Field


AuthRole = Literal["field_tech", "manager", "engineer"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    role: AuthRole
    username: str


class AuthenticatedUser(BaseModel):
    username: str
    role: AuthRole
