from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from auth import dto, service
from common import erri
from middleware import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@auth.exempt
@router.post("/login", response_model=dto.LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dto.LoginResponse:
    """Authenticate user and return access and refresh tokens."""
    try:
        token_pair = service.login_user(form_data.username, form_data.password)
        return dto.LoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        )
    except erri.BusinessError as e:
        # OAuth2 standard error format (RFC 6749 Section 5.2)
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_grant", "error_description": e.detail},
        ) from None


@auth.exempt
@router.post("/refresh", response_model=dto.RefreshTokenResponse)
async def refresh(body: dto.RefreshTokenRequest) -> dto.RefreshTokenResponse:
    """Refresh access token using a valid refresh token.

    Implements Token Rotation: the old refresh token is revoked and a new one is issued.
    """
    try:
        token_pair = service.refresh_tokens(body.refresh_token)
        return dto.RefreshTokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        )
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@auth.exempt
@router.post("/logout", response_model=dto.LogoutResponse)
async def logout(body: dto.RefreshTokenRequest) -> dto.LogoutResponse:
    """Logout by revoking the refresh token."""
    service.revoke_token(body.refresh_token)
    return dto.LogoutResponse()
