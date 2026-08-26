from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.aliyun_models import generate_image, generate_text
from app.auth import get_current_user
from app.core.database import get_db
from app.models import ModelConfiguration, User
from app.schemas import ModelConfigurationCreate, ModelConfigurationRead, ModelConfigurationUpdate, ModelTestRequest, ModelTestResult

router = APIRouter(prefix="/api/v1/models", tags=["模型管理"])


def accessible(model: ModelConfiguration | None, user: User, write: bool = False) -> ModelConfiguration:
    if not model:
        raise HTTPException(404, "模型配置不存在")
    if user.role == "admin":
        return model
    if model.owner_user_id == user.id or (not write and model.owner_user_id is None):
        return model
    raise HTTPException(403, "无权操作该模型配置")


@router.get("", response_model=list[ModelConfigurationRead], summary="查询系统模型和我的模型")
def list_models(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(ModelConfiguration).order_by(ModelConfiguration.capability, ModelConfiguration.name)
    if user.role != "admin":
        query = query.where(or_(ModelConfiguration.owner_user_id.is_(None), ModelConfiguration.owner_user_id == user.id))
    return list(db.scalars(query))


@router.post("", response_model=ModelConfigurationRead, status_code=201, summary="添加我的模型")
def create_model(data: ModelConfigurationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    model = ModelConfiguration(owner_user_id=user.id, **data.model_dump(), is_default=False)
    db.add(model); db.commit(); db.refresh(model)
    return model


@router.put("/{model_id}", response_model=ModelConfigurationRead, summary="修改我的模型")
def update_model(model_id: str, data: ModelConfigurationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    model = accessible(db.get(ModelConfiguration, model_id), user, write=True)
    if data.is_default and not data.enabled:
        raise HTTPException(422, "默认模型必须处于启用状态")
    if data.is_default:
        db.execute(update(ModelConfiguration).where(
            ModelConfiguration.capability == (data.capability or model.capability),
            ModelConfiguration.owner_user_id == model.owner_user_id,
        ).values(is_default=False))
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "api_key" and not value:
            continue
        setattr(model, field, value)
    db.commit(); db.refresh(model)
    return model


@router.delete("/{model_id}", status_code=204, summary="删除我的模型")
def delete_model(model_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    model = accessible(db.get(ModelConfiguration, model_id), user, write=True)
    if model.owner_user_id is None:
        raise HTTPException(409, "系统预置模型不能删除，只能停用")
    db.delete(model); db.commit()
    return Response(status_code=204)


@router.post("/{model_id}/test", response_model=ModelTestResult, summary="测试模型调用", description="会产生一次真实模型调用和对应费用。")
def test_model(model_id: str, data: ModelTestRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    model = accessible(db.get(ModelConfiguration, model_id), user)
    if not model.enabled:
        raise HTTPException(404, "模型未启用")
    try:
        if model.capability == "text":
            output_text, latency = generate_text(model, data.prompt, model.api_key)
            return ModelTestResult(status="success", model=model.model, output_text=output_text, latency_ms=latency)
        _, output_url, latency = generate_image(model, data.prompt, api_key=model.api_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"模型调用失败：{exc}") from exc
    return ModelTestResult(status="success", model=model.model, output_url=output_url, latency_ms=latency)
