from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import PERMISSIONS, get_current_user, hash_password, require_permission
from app.core.database import get_db
from app.models import User
from app.schemas import PasswordReset, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["用户权限"])


def validate_permissions(codes: list[str]) -> None:
    invalid = sorted(set(codes) - set(PERMISSIONS))
    if invalid:
        raise HTTPException(422, f"无效权限码：{', '.join(invalid)}")


@router.get("/permissions", summary="查询可分配权限")
def list_permissions(_: User = Depends(require_permission("users:manage"))):
    return [{"code": code, "name": name} for code, name in PERMISSIONS.items()]


@router.get("", response_model=list[UserRead], summary="查询用户列表")
def list_users(_: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.post("", response_model=UserRead, status_code=201, summary="创建用户")
def create_user(data: UserCreate, _: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(409, "用户名已经存在")
    validate_permissions(data.permission_codes)
    user = User(username=data.username, display_name=data.display_name, password_hash=hash_password(data.password), role=data.role,
                permissions_csv=",".join(sorted(set(data.permission_codes))))
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserRead, summary="修改用户和权限")
def update_user(user_id: str, data: UserUpdate, current: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == current.id and data.status == "disabled":
        raise HTTPException(409, "不能停用当前登录账号")
    validate_permissions(data.permission_codes)
    user.display_name = data.display_name; user.role = data.role; user.status = data.status
    user.permissions_csv = "*" if data.role == "admin" else ",".join(sorted(set(data.permission_codes)))
    db.commit(); db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserRead, summary="重置用户密码")
def reset_password(user_id: str, data: PasswordReset, _: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    user.password_hash = hash_password(data.password); db.commit(); db.refresh(user)
    return user
