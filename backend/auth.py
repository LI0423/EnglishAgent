import os
import time
import hmac
import hashlib
import base64
import json
from typing import Optional, Dict


# Simple JWT (HS256) without external deps
SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(sub: str, expires_in: int = 3600, extra: Optional[Dict] = None) -> str:
    header = {"typ": "JWT", "alg": ALGORITHM}
    now = int(time.time())
    payload = {"sub": sub, "iat": now, "exp": now + expires_in}
    if extra:
        payload.update(extra)
    header_b64 = _b64url(json.dumps(header, separators=(',', ':')).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(',', ':')).encode())
    to_sign = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(SECRET_KEY.encode(), to_sign, hashlib.sha256).digest()
    sig_b64 = _b64url(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_token(token: str) -> Optional[Dict]:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        to_sign = f"{header_b64}.{payload_b64}".encode()
        expected = hmac.new(SECRET_KEY.encode(), to_sign, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# Password hashing (demo): salted sha256
def hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = os.urandom(8).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split('$', 1)
        return hash_password(password, salt) == hashed
    except Exception:
        return False


