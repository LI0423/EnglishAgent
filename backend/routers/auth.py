from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..auth import create_access_token, hash_password, verify_password, decode_token
from ..redis_client import save_token, get_user_by_token
from ..db import get_user_by_username, create_user, get_user_by_id


router = APIRouter()

DEMO_BOOTSTRAPPED = False


class LoginRequest(BaseModel):
    username: str
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
    row = get_user_by_username(req.username)
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


