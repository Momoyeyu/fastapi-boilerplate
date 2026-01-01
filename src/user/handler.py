from fastapi import APIRouter, HTTPException, Request, Response

from common import erri
from user import dto
from user import service
from middleware import auth

router = APIRouter(prefix="/user", tags=["user"])

@auth.exempt
@router.post("/register", response_model=dto.UserRegisterResponse)
async def register(request: Request, body: dto.UserRegisterRequest):
    try:
        user = service.register_user(body.username, body.password)
        return dto.UserRegisterResponse(id=user.id, username=user.username)
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@auth.exempt
@router.post("/login", response_model=dto.UserLoginResponse)
async def login(request: Request, body: dto.UserLoginRequest, response: Response):
    try:
        token = service.login_user(body.username, body.password)
        response.headers["x-jwt-token"] = token
        return dto.UserLoginResponse()
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/whoami", response_model=dto.UserWhoAmIResponse)
async def whoami(request: Request):
    try:
        username = auth.get_username(request)
        return dto.UserWhoAmIResponse(username=username)
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/me", response_model=dto.UserProfileResponse)
async def get_me(request: Request):
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
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/me", response_model=dto.UserProfileResponse)
async def update_me(request: Request, body: dto.UserProfileUpdateRequest):
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
        raise HTTPException(status_code=e.status_code, detail=e.detail)
