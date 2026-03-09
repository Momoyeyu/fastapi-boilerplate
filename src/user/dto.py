from pydantic import BaseModel


class UserWhoAmIResponse(BaseModel):
    username: str


class UserProfileResponse(BaseModel):
    username: str
    nickname: str | None
    email: str
    avatar_url: str | None
    role: str
    is_active: bool


class UserProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str
