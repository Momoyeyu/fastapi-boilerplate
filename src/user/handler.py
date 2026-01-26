from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from common import erri
from middleware import auth
from user import dto, service

router = APIRouter(prefix="/user", tags=["user"])


@auth.exempt
@router.post("/register", response_model=dto.UserRegisterResponse)
async def register(body: dto.UserRegisterRequest) -> dto.UserRegisterResponse:
    try:
        user = service.register_user(body.username, body.password)
        assert user.id is not None  # guaranteed by service
        return dto.UserRegisterResponse(id=user.id, username=user.username)
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@auth.exempt
@router.post("/login", response_model=dto.UserLoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dto.UserLoginResponse:
    try:
        token_pair = service.login_user(form_data.username, form_data.password)
        return dto.UserLoginResponse(
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
        token_pair = auth.refresh_tokens(body.refresh_token)
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
    auth.revoke_token(body.refresh_token)
    return dto.LogoutResponse()


@router.get("/whoami", response_model=dto.UserWhoAmIResponse)
async def whoami(request: Request) -> dto.UserWhoAmIResponse:
    try:
        username = auth.get_username(request)
        return dto.UserWhoAmIResponse(username=username)
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/me", response_model=dto.UserProfileResponse)
async def get_me(request: Request) -> dto.UserProfileResponse:
    try:
        username = auth.get_username(request)
        user = service.get_user_profile(username)
        return dto.UserProfileResponse(
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
        )
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.patch("/me", response_model=dto.UserProfileResponse)
async def update_me(request: Request, body: dto.UserProfileUpdateRequest) -> dto.UserProfileResponse:
    try:
        username = auth.get_username(request)
        user = service.update_my_profile(
            username,
            nickname=body.nickname,
            email=body.email,
            avatar_url=body.avatar_url,
        )
        return dto.UserProfileResponse(
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
        )
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
