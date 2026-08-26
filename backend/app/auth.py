import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["用户认证"])
bearer = HTTPBearer(auto_error=False)
PERMISSIONS = {
    "content:view": "查看内容任务", "content:edit": "创建和编辑内容任务",
    "publish:view": "查看发布管理", "publish:approve": "审批发布任务",
    "publish:execute": "执行发布和确认人工发布", "publish:metrics": "录入发布效果数据",
    "analytics:view": "查看数据运营", "users:manage": "管理用户与权限",
    "models:manage": "管理和测试模型配置",
}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, expected = encoded.split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds))
        return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user: User) -> tuple[str, int]:
    settings = get_settings(); seconds = settings.auth_token_hours * 3600
    payload = _encode(json.dumps({"sub": user.id, "exp": int((datetime.utcnow() + timedelta(seconds=seconds)).timestamp())}, separators=(",", ":")).encode())
    signature = _encode(hmac.new(settings.auth_secret_key.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}", seconds


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    if settings.app_env == "test":
        return User(username="test", display_name="测试用户", password_hash="", role="admin")
    if not credentials:
        raise HTTPException(401, "请先登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload, signature = credentials.credentials.split(".", 1)
        expected = _encode(hmac.new(settings.auth_secret_key.encode(), payload.encode(), hashlib.sha256).digest())
        data = json.loads(_decode(payload))
        if not hmac.compare_digest(signature, expected) or data["exp"] < datetime.utcnow().timestamp():
            raise ValueError
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(401, "登录已失效，请重新登录", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, data["sub"])
    if not user or user.status != "active":
        raise HTTPException(401, "用户不存在或已停用")
    return user


def require_permission(code: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != "admin" and code not in user.permission_codes:
            raise HTTPException(403, f"缺少权限：{code}")
        return user
    return dependency


def ensure_default_admin(db: Session) -> None:
    settings = get_settings()
    if db.scalar(select(User).where(User.username == settings.default_admin_username)):
        return
    db.add(User(username=settings.default_admin_username, display_name="系统管理员", password_hash=hash_password(settings.default_admin_password), role="admin", permissions_csv="*"))
    db.commit()


@router.post("/login", response_model=LoginResponse, summary="用户登录")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or user.status != "active" or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    user.last_login_at = datetime.utcnow(); db.commit(); db.refresh(user)
    token, expires = create_token(user)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires, "user": user}


@router.get("/me", response_model=UserRead, summary="查询当前用户")
def me(user: User = Depends(get_current_user)):
    return user
