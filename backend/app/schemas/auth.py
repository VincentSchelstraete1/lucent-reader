from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str | None
    email_verified: bool
    display_name: str | None
    avatar_url: str | None


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class SessionMetadata(BaseModel):
    expires_at: datetime
