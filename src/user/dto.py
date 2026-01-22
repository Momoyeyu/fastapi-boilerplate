from pydantic import BaseModel


class UserRegisterRequest(BaseModel):
    username: str
    password: str


class UserRegisterResponse(BaseModel):
    id: int
    username: str


class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserWhoAmIResponse(BaseModel):
    username: str


class UserProfileResponse(BaseModel):
    username: str
    nickname: str | None
    email: str | None
    avatar_url: str | None
    role: str
    is_active: bool


class UserProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    email: str | None = None
    avatar_url: str | None = None
