from fastapi import APIRouter, HTTPException, Request

from common import erri
from middleware import auth
from user import dto, service

router = APIRouter(prefix="/user", tags=["user"])


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


@router.post("/me", response_model=dto.UserProfileResponse)
async def update_me(request: Request, body: dto.UserProfileUpdateRequest) -> dto.UserProfileResponse:
    try:
        username = auth.get_username(request)
        user = service.update_my_profile(
            username,
            nickname=body.nickname,
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


@router.post("/password/change", response_model=dto.PasswordChangeResponse)
async def change_password(request: Request, body: dto.PasswordChangeRequest) -> dto.PasswordChangeResponse:
    try:
        username = auth.get_username(request)
        service.change_password(username, body.old_password, body.new_password)
        return dto.PasswordChangeResponse()
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
