from fastapi import APIRouter, Request

from common.resp import Response, ok
from middleware import auth
from user import dto, profile

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/whoami")
async def whoami(request: Request) -> Response:
    username = auth.get_username(request)
    return ok(data=dto.UserWhoAmIResponse(username=username).model_dump())


@router.get("/me")
async def get_me(request: Request) -> Response:
    username = auth.get_username(request)
    user = profile.get_user_profile(username)
    return ok(
        data=dto.UserProfileResponse(
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
        ).model_dump()
    )


@router.post("/me")
async def update_me(request: Request, body: dto.UserProfileUpdateRequest) -> Response:
    username = auth.get_username(request)
    user = profile.update_my_profile(
        username,
        nickname=body.nickname,
        avatar_url=body.avatar_url,
    )
    return ok(
        data=dto.UserProfileResponse(
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            avatar_url=user.avatar_url,
            role=user.role,
            is_active=user.is_active,
        ).model_dump()
    )


@router.post("/password/change")
async def change_password(request: Request, body: dto.PasswordChangeRequest) -> Response:
    username = auth.get_username(request)
    profile.change_password(username, body.old_password, body.new_password)
    return ok(message="Password changed successfully")
