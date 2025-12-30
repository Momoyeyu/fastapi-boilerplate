from fastapi import APIRouter, HTTPException

from common import erri
from user import dto
from user import service
from middleware import auth

router = APIRouter(prefix="/user", tags=["user"])

@auth.exempt("/user/register")
@router.post("/register", response_model=dto.UserRegisterResponse)
async def register(request: dto.UserRegisterRequest):
    try:
        user = service.register_user(request.username, request.password)
        return dto.UserRegisterResponse(id=user.id, username=user.username)
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.msg)

@auth.exempt("/user/login")
@router.post("/login", response_model=dto.UserLoginResponse)
async def login(request: dto.UserLoginRequest):
    try:
        token = service.login_user(request.username, request.password)
        return dto.UserLoginResponse(token=token)
    except erri.BusinessError as e:
        raise HTTPException(status_code=e.status_code, detail=e.msg)
