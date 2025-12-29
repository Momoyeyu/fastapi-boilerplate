from fastapi import APIRouter, HTTPException

from user import dto
from user import error
from user import service
from middleware import auth

router = APIRouter(prefix="/user", tags=["user"])

@auth.exempt("/user/register")
@router.post("/register", response_model=dto.UserRegisterResponse)
async def register(request: dto.UserRegisterRequest):
    try:
        user = service.register_user(request.username, request.password)
        return dto.UserRegisterResponse(id=user.id, username=user.username)
    except error.UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except error.CreateUserFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))

@auth.exempt("/user/login")
@router.post("/login", response_model=dto.UserLoginResponse)
async def login(request: dto.UserLoginRequest):
    try:
        token = service.login_user(request.username, request.password)
        return dto.UserLoginResponse(token=token)
    except error.InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))
