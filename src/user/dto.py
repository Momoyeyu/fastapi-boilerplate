from typing import Optional

from pydantic import BaseModel

class UserRegisterRequest(BaseModel):
    username: str
    password: str

class UserRegisterResponse(BaseModel):
    id: int
    username: str

class UserLoginRequest(BaseModel):
    username: str
    password: str

class UserLoginResponse(BaseModel):
    pass


class UserWhoAmIResponse(BaseModel):
    username: str


class UserProfileResponse(BaseModel):
    username: str
    nickname: Optional[str]
    email: Optional[str]
    avatar_url: Optional[str]
    role: str
    is_active: bool


class UserProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
