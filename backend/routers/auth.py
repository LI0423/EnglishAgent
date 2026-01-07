from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..auth import create_access_token, hash_password, verify_password, decode_token, register
from ..redis_client import save_token, get_user_by_token
from ..db import get_user_by_username, create_user, get_user_by_id, get_user_by_phone


router = APIRouter()

DEMO_BOOTSTRAPPED = False


class LoginRequest(BaseModel):
    username: Optional[str] = None
    phone: Optional[str] = None
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    global DEMO_BOOTSTRAPPED
    # bootstrap demo user once
    if not DEMO_BOOTSTRAPPED and not get_user_by_username("demo"):
        create_user("u_demo", "demo", hash_password("demo"))
        DEMO_BOOTSTRAPPED = True
    
    # 优先使用手机号登录
    if req.phone:
        row = get_user_by_phone(req.phone)
    elif req.username:
        row = get_user_by_username(req.username)
    else:
        raise HTTPException(status_code=400, detail="Either username or phone is required")
    
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=row["id"], expires_in=3600)
    save_token(row["id"], token, ttl=3600)
    return LoginResponse(token=token)


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


@router.post("/register", response_model=LoginResponse)
async def register(req: RegisterRequest):
    if get_user_by_username(req.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    user_id = f"u_{req.username}"
    ok, err = create_user(user_id, req.username, hash_password(req.password), req.email)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Register failed: {err}")
    token = create_access_token(sub=user_id, expires_in=3600)
    save_token(user_id, token, ttl=3600)
    return LoginResponse(token=token)


class PhoneRegisterRequest(BaseModel):
    phone: str
    password: str


class PhoneRegisterResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


@router.post("/register/phone", response_model=PhoneRegisterResponse)
async def phone_register(req: PhoneRegisterRequest):
    from ..auth import register as phone_register_func
    result = phone_register_func(req.phone, req.password)
    return PhoneRegisterResponse(**result)


class MeResponse(BaseModel):
    userId: str
    username: str


@router.get("/me", response_model=MeResponse)
async def me(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = get_user_by_token(token) or payload.get("sub")
    row = get_user_by_id(str(user_id))
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return MeResponse(userId=str(user_id), username=row["username"])


