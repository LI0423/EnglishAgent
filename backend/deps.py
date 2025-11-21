from typing import Optional
from fastapi import Header, HTTPException
from .auth import decode_token
from .redis_client import get_user_by_token
from .db import get_user_by_id


def get_current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = get_user_by_token(token) or payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user = get_user_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"id": user["id"], "username": user["username"]}


