from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import secrets
import time
from ..auth import create_access_token, hash_password, verify_password, decode_token, register
from ..redis_client import save_token, get_user_by_token
from ..db import (
    get_user_by_username,
    create_user,
    get_user_by_id,
    get_user_by_phone,
    get_user_by_email,
    update_user_password_hash,
    create_password_reset_token,
    get_password_reset_token,
    delete_password_reset_token,
    cleanup_expired_password_reset_tokens,
    count_recent_password_reset_attempts,
    record_password_reset_attempt,
    cleanup_expired_password_reset_codes,
    create_password_reset_code,
    delete_password_reset_code,
    get_password_reset_code,
    increment_password_reset_code_attempts,
)
from ..services.reminder_service import get_reminder_service


router = APIRouter()

DEMO_BOOTSTRAPPED = False
PASSWORD_RESET_TTL_SECONDS = 15 * 60
EXPOSE_RESET_TOKEN = os.environ.get("AUTH_EXPOSE_RESET_TOKEN", "0").strip() in {"1", "true", "True"}
PASSWORD_RESET_RATE_WINDOW_SECONDS = int(os.environ.get("AUTH_RESET_RATE_WINDOW_SECONDS", "3600"))
PASSWORD_RESET_RATE_LIMIT = int(os.environ.get("AUTH_RESET_RATE_LIMIT", "5"))
PASSWORD_RESET_CODE_TTL_SECONDS = int(os.environ.get("AUTH_RESET_CODE_TTL_SECONDS", "600"))
PASSWORD_RESET_CODE_MAX_ATTEMPTS = int(os.environ.get("AUTH_RESET_CODE_MAX_ATTEMPTS", "5"))
EXPOSE_RESET_CODE = os.environ.get("AUTH_EXPOSE_RESET_CODE", "0").strip() in {"1", "true", "True"}


class LoginRequest(BaseModel):
    username: Optional[str] = None
    phone: Optional[str] = None
    password: str


class LoginResponse(BaseModel):
    token: str
    access_token: str
    token_type: str = "bearer"


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
    return LoginResponse(token=token, access_token=token)


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
    return LoginResponse(token=token, access_token=token)


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


class PasswordResetRequest(BaseModel):
    account: str


class PasswordResetRequestResponse(BaseModel):
    success: bool
    message: str
    reset_token: Optional[str] = None
    expires_in: Optional[int] = None


class PasswordResetConfirm(BaseModel):
    reset_token: str
    new_password: str


class PasswordResetConfirmResponse(BaseModel):
    success: bool
    message: str


class PasswordResetCodeRequest(BaseModel):
    account: str
    channel: str = "email"  # email / sms


class PasswordResetCodeRequestResponse(BaseModel):
    success: bool
    message: str
    verification_code: Optional[str] = None
    expires_in: Optional[int] = None


class PasswordResetCodeConfirm(BaseModel):
    account: str
    code: str
    new_password: str


def _find_user_by_account(account: str):
    value = (account or "").strip()
    if not value:
        return None
    return get_user_by_username(value) or get_user_by_phone(value) or get_user_by_email(value)


def _normalize_account_key(account: str) -> str:
    return (account or "").strip().lower()


@router.post("/password/reset/request", response_model=PasswordResetRequestResponse)
async def request_password_reset(req: PasswordResetRequest):
    now = int(time.time())
    cleanup_expired_password_reset_tokens(now)
    account_key = _normalize_account_key(req.account)
    recent_attempts = count_recent_password_reset_attempts(
        account_key,
        window_seconds=PASSWORD_RESET_RATE_WINDOW_SECONDS,
    )
    record_password_reset_attempt(account_key, requested_at=now)

    if recent_attempts >= PASSWORD_RESET_RATE_LIMIT:
        return PasswordResetRequestResponse(
            success=True,
            message="请求过于频繁，请稍后再试。",
        )

    row = _find_user_by_account(req.account)

    # 保持响应一致，避免暴露账户是否存在
    if not row:
        return PasswordResetRequestResponse(
            success=True,
            message="如果账户存在，重置链接已发送。",
        )

    reset_token = secrets.token_urlsafe(24)
    create_password_reset_token(reset_token, str(row["id"]), now + PASSWORD_RESET_TTL_SECONDS)
    return PasswordResetRequestResponse(
        success=True,
        message="已生成重置凭证，请在有效期内完成重置。",
        reset_token=reset_token if EXPOSE_RESET_TOKEN else None,
        expires_in=PASSWORD_RESET_TTL_SECONDS if EXPOSE_RESET_TOKEN else None,
    )


@router.post("/password/reset/code/request", response_model=PasswordResetCodeRequestResponse)
async def request_password_reset_code(req: PasswordResetCodeRequest):
    now = int(time.time())
    cleanup_expired_password_reset_codes(now)
    account_key = _normalize_account_key(req.account)
    recent_attempts = count_recent_password_reset_attempts(
        account_key,
        window_seconds=PASSWORD_RESET_RATE_WINDOW_SECONDS,
    )
    record_password_reset_attempt(account_key, requested_at=now)
    if recent_attempts >= PASSWORD_RESET_RATE_LIMIT:
        return PasswordResetCodeRequestResponse(success=True, message="请求过于频繁，请稍后再试。")

    row = _find_user_by_account(req.account)
    if not row:
        return PasswordResetCodeRequestResponse(success=True, message="如果账户存在，验证码已发送。")

    channel = (req.channel or "email").strip().lower()
    if channel not in {"email", "sms"}:
        raise HTTPException(status_code=400, detail="Unsupported reset channel")

    target_email = str(row["email"] or "").strip() if "email" in row.keys() else ""
    target_phone = str(row["phone"] or "").strip() if "phone" in row.keys() else ""
    if channel == "email" and not target_email:
        return PasswordResetCodeRequestResponse(success=True, message="如果账户存在，验证码已发送。")
    if channel == "sms" and not target_phone:
        return PasswordResetCodeRequestResponse(success=True, message="如果账户存在，验证码已发送。")

    code = f"{secrets.randbelow(1000000):06d}"
    create_password_reset_code(
        account_key=account_key,
        user_id=str(row["id"]),
        channel=channel,
        code=code,
        expires_at=now + PASSWORD_RESET_CODE_TTL_SECONDS,
    )

    reminder = {
        "user_id": str(row["id"]),
        "title": "EnglishAgent 密码重置验证码",
        "content": f"你的验证码是 {code}，{PASSWORD_RESET_CODE_TTL_SECONDS // 60} 分钟内有效。",
        "channel": channel,
        "metadata": {
            "email": target_email,
            "phone": target_phone,
            "purpose": "password_reset",
        },
    }
    sent_ok = get_reminder_service().send_reminder(reminder)
    if not sent_ok:
        # 离线/测试环境下发送渠道可能不可用，此时保留已签发验证码用于后续确认流程
        return PasswordResetCodeRequestResponse(
            success=True,
            message="验证码发送通道暂不可用，已生成验证码。",
            verification_code=code if EXPOSE_RESET_CODE else None,
            expires_in=PASSWORD_RESET_CODE_TTL_SECONDS if EXPOSE_RESET_CODE else None,
        )

    return PasswordResetCodeRequestResponse(
        success=True,
        message="验证码已发送，请查收。",
        verification_code=code if EXPOSE_RESET_CODE else None,
        expires_in=PASSWORD_RESET_CODE_TTL_SECONDS if EXPOSE_RESET_CODE else None,
    )


@router.post("/password/reset/confirm", response_model=PasswordResetConfirmResponse)
async def confirm_password_reset(req: PasswordResetConfirm):
    now = int(time.time())
    cleanup_expired_password_reset_tokens(now)
    token_meta = get_password_reset_token(req.reset_token)
    if not token_meta or int(token_meta["expires_at"]) <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    new_password = (req.new_password or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password length must be at least 6")

    user_id = str(token_meta["user_id"])
    ok = update_user_password_hash(user_id, hash_password(new_password))
    delete_password_reset_token(req.reset_token)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to reset password")

    return PasswordResetConfirmResponse(success=True, message="Password has been reset")


@router.post("/password/reset/code/confirm", response_model=PasswordResetConfirmResponse)
async def confirm_password_reset_by_code(req: PasswordResetCodeConfirm):
    now = int(time.time())
    cleanup_expired_password_reset_codes(now)
    account_key = _normalize_account_key(req.account)
    row = get_password_reset_code(account_key)
    if not row or int(row["expires_at"]) <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    code = (req.code or "").strip()
    if not code or code != str(row["code"]):
        attempts = increment_password_reset_code_attempts(account_key)
        if attempts >= PASSWORD_RESET_CODE_MAX_ATTEMPTS:
            delete_password_reset_code(account_key)
        raise HTTPException(status_code=400, detail="Invalid verification code")

    new_password = (req.new_password or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password length must be at least 6")

    ok = update_user_password_hash(str(row["user_id"]), hash_password(new_password))
    delete_password_reset_code(account_key)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to reset password")
    return PasswordResetConfirmResponse(success=True, message="Password has been reset")
