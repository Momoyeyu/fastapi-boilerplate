from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    message: str = "Verification code sent"


class RegisterVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token_expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token_expires_in: int


class LogoutResponse(BaseModel):
    message: str = "Successfully logged out"


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordForgotResponse(BaseModel):
    message: str = "If the email is registered, a verification code has been sent"


class PasswordResetRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class PasswordResetResponse(BaseModel):
    message: str = "Password reset successfully"
