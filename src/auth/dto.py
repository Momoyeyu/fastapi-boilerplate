from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    invitation_code: str | None = None


class RegisterVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    password: str


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token_expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str
