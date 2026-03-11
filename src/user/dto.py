from pydantic import BaseModel


class UserWhoAmIResponse(BaseModel):
    username: str


class UserProfileResponse(BaseModel):
    username: str
    email: str
    avatar_url: str | None
    is_active: bool


class UserProfileUpdateRequest(BaseModel):
    avatar_url: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str
