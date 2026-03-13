from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from auth import dto, service
from common.resp import Response, ok
from conf.config import settings
from middleware import auth
from tenant import service as tenant_service

router = APIRouter(prefix="/auth", tags=["auth"])


@auth.exempt
@router.post("/register")
async def register_user(body: dto.RegisterRequest) -> Response:
    """Initiate registration by sending a verification code to email."""
    await service.initiate_registration(body.email, body.password, body.invitation_code)
    return ok(message="Verification code sent")


@auth.exempt
@router.post("/register/verify")
async def register_verify(body: dto.RegisterVerifyRequest) -> Response:
    """Complete registration after email verification."""
    token_pair = await service.complete_registration(body.email, body.code, body.password)
    return ok(
        data=dto.TokenData(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        ).model_dump()
    )


@auth.exempt
@router.post("/login")
async def login(body: dto.LoginRequest) -> Response:
    """Authenticate user and return access and refresh tokens.

    Supports login with email or username via JSON body.
    """
    token_pair = await service.login_user(body.identifier, body.password)
    return ok(
        data=dto.TokenData(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        ).model_dump()
    )


if settings.debug:

    @auth.exempt
    @router.post("/swagger/login", tags=["swagger"], include_in_schema=True)
    async def swagger_login(form_data: OAuth2PasswordRequestForm = Depends()) -> Response:
        """OAuth2-compatible login for Swagger UI. Only available in debug mode."""
        token_pair = await service.login_user(form_data.username, form_data.password)
        return ok(
            data=dto.TokenData(
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                expires_in=token_pair.expires_in,
                refresh_token_expires_in=token_pair.refresh_token_expires_in,
            ).model_dump()
        )


@auth.exempt
@router.post("/token/refresh")
async def refresh(body: dto.RefreshTokenRequest) -> Response:
    """Refresh access token using a valid refresh token.

    Implements Token Rotation: the old refresh token is revoked and a new one is issued.
    """
    token_pair = service.refresh_tokens(body.refresh_token)
    return ok(
        data=dto.TokenData(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        ).model_dump()
    )


@auth.exempt
@router.post("/logout")
async def logout(body: dto.RefreshTokenRequest) -> Response:
    """Logout by revoking the refresh token."""
    service.revoke_token(body.refresh_token)
    return ok(message="Successfully logged out")


@auth.exempt
@router.post("/password/forgot")
async def password_forgot(body: dto.PasswordForgotRequest) -> Response:
    """Request password reset by sending a verification code."""
    await service.request_password_reset(body.email)
    return ok(message="If the email is registered, a verification code has been sent")


@auth.exempt
@router.post("/password/reset")
async def password_reset(body: dto.PasswordResetRequest) -> Response:
    """Reset password after email verification."""
    await service.reset_password(body.email, body.code, body.new_password)
    return ok(message="Password reset successfully")


@auth.exempt
@router.post("/invite/accept")
async def accept_invite(body: dto.InviteAcceptRequest) -> Response:
    """Accept a tenant invitation. Creates a new account and joins the tenant."""
    token_pair = await tenant_service.accept_invitation(body.token, body.password)
    return ok(
        data=dto.TokenData(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        ).model_dump()
    )
