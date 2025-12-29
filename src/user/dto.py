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
    token: str
    token_type: str = "Bearer"
