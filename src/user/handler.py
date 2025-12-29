from fastapi import APIRouter, HTTPException

from src.user import dto
from src.user.model import create_user, get_user
from src.user import service
from src.middleware import auth

router = APIRouter(prefix="/user", tags=["user"])

@auth.exempt("/user/register")
@router.post("/register", response_model=dto.UserRegisterResponse)
async def register(request: dto.UserRegisterRequest):
    if get_user(request.username):
        raise HTTPException(status_code=409, detail="User already exists")
    encrypted_password = service.get_password_hash(request.password)
    user = create_user(request.username, encrypted_password)
    if not user or user.id is None:
        raise HTTPException(status_code=500, detail="Create user failed")
    return dto.UserRegisterResponse(id=user.id, username=user.username)

@auth.exempt("/user/login")
@router.post("/login", response_model=dto.UserLoginResponse)
async def login(request: dto.UserLoginRequest):
    user = get_user(request.username)
    encrypted_password = service.get_password_hash(request.password)
    if not user or user.password != encrypted_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth.create_token({"id": user.id, "username": user.username})
    return dto.UserLoginResponse(token=token)
