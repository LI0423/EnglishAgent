import os
import re
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from backend.db import create_user, get_user_by_phone


# JWT configuration
SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"


def create_access_token(sub: str, expires_in: int = 3600, extra: Optional[Dict] = None) -> str:
    """创建访问令牌"""
    to_encode = {"sub": sub, "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)}
    if extra:
        to_encode.update(extra)
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict]:
    """解码令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_password(password: str) -> str:
    """哈希密码"""
    # bcrypt要求密码不能超过72字节，需要截断
    password = password[:72]
    # 直接使用bcrypt库
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    # bcrypt要求密码不能超过72字节，需要截断
    password = password[:72]
    # 直接使用bcrypt库
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def validate_phone(phone: str) -> bool:
    """验证手机号格式"""
    # 中国大陆手机号格式验证
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def generate_username(phone: str) -> str:
    """基于手机号生成用户名"""
    # 使用手机号后8位作为用户名
    suffix = phone[-8:]
    return f"user_{suffix}"


def register(phone: str, password: str) -> Dict[str, Any]:
    """用户注册
    
    Args:
        phone: 手机号
        password: 密码
        
    Returns:
        Dict: 注册结果
    """
    
    # 验证手机号格式
    if not validate_phone(phone):
        return {
            "success": False,
            "message": "手机号格式不正确"
        }
    
    # 检查手机号是否已注册
    if get_user_by_phone(phone):
        return {
            "success": False,
            "message": "手机号已注册"
        }
    
    # 生成用户ID和用户名
    user_id = str(uuid.uuid4())
    username = generate_username(phone)
    
    # 哈希密码
    password_hash = hash_password(password)
    
    # 创建用户
    success, error = create_user(user_id, username, password_hash, phone=phone)
    
    if not success:
        return {
            "success": False,
            "message": f"注册失败: {error}"
        }
    
    # 生成访问令牌
    access_token = create_access_token(user_id, extra={
        "phone": phone,
        "username": username
    })
    
    return {
        "success": True,
        "message": "注册成功",
        "data": {
            "user_id": user_id,
            "username": username,
            "phone": phone,
            "access_token": access_token
        }
    }


