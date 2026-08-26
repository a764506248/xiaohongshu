import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.core.database import get_db
from app.models import PromptTemplate, PromptVersion, User
from app.schemas import PromptRollbackRequest, PromptTemplateCreate, PromptTemplateRead, PromptTemplateUpdate, PromptVersionRead

router = APIRouter(prefix="/api/v1/prompts", tags=["Prompt 管理"])


def query_with_versions():
    return select(PromptTemplate).options(selectinload(PromptTemplate.versions))


def accessible(prompt: PromptTemplate | None, user: User, write: bool = False) -> PromptTemplate:
    if not prompt: raise HTTPException(404, "Prompt 不存在")
    if user.role == "admin" or prompt.owner_user_id == user.id or (not write and prompt.owner_user_id is None): return prompt
    raise HTTPException(403, "无权操作该 Prompt")


def set_default(db: Session, prompt: PromptTemplate) -> None:
    db.execute(update(PromptTemplate).where(PromptTemplate.prompt_key == prompt.prompt_key, PromptTemplate.owner_user_id == prompt.owner_user_id).values(is_default=False))
    prompt.is_default = True


@router.get("", response_model=list[PromptTemplateRead], summary="查询系统 Prompt 和我的 Prompt")
def list_prompts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = query_with_versions().order_by(PromptTemplate.scene, PromptTemplate.name)
    if user.role != "admin": query = query.where(or_(PromptTemplate.owner_user_id.is_(None), PromptTemplate.owner_user_id == user.id))
    return list(db.scalars(query).unique())


@router.post("", response_model=PromptTemplateRead, status_code=201, summary="创建我的 Prompt")
def create_prompt(data: PromptTemplateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    values = data.model_dump(exclude={"tags","system_prompt","user_prompt_template","variables","change_note"})
    prompt = PromptTemplate(owner_user_id=user.id, tags_csv=",".join(dict.fromkeys(data.tags)), **values)
    db.add(prompt); db.flush()
    db.add(PromptVersion(prompt_template_id=prompt.id,version_number=1,system_prompt=data.system_prompt,user_prompt_template=data.user_prompt_template,variables_json=json.dumps(data.variables,ensure_ascii=False),change_note=data.change_note,created_by=user.id))
    if data.is_default: set_default(db,prompt)
    db.commit()
    return db.scalar(query_with_versions().where(PromptTemplate.id==prompt.id))


@router.put("/{prompt_id}", response_model=PromptTemplateRead, summary="更新 Prompt 并创建新版本")
def update_prompt(prompt_id: str, data: PromptTemplateUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prompt=accessible(db.scalar(query_with_versions().where(PromptTemplate.id==prompt_id)),user,write=True)
    prompt.name=data.name;prompt.tags_csv=",".join(dict.fromkeys(data.tags));prompt.scene=data.scene;prompt.model_capability=data.model_capability;prompt.description=data.description;prompt.status=data.status
    next_version=(db.scalar(select(func.max(PromptVersion.version_number)).where(PromptVersion.prompt_template_id==prompt.id)) or 0)+1
    db.add(PromptVersion(prompt_template_id=prompt.id,version_number=next_version,system_prompt=data.system_prompt,user_prompt_template=data.user_prompt_template,variables_json=json.dumps(data.variables,ensure_ascii=False),change_note=data.change_note,created_by=user.id))
    if data.is_default: set_default(db,prompt)
    else: prompt.is_default=False
    db.commit();return db.scalar(query_with_versions().where(PromptTemplate.id==prompt.id))


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionRead], summary="查询 Prompt 版本历史")
def versions(prompt_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    prompt=accessible(db.get(PromptTemplate,prompt_id),user);return list(db.scalars(select(PromptVersion).where(PromptVersion.prompt_template_id==prompt.id).order_by(PromptVersion.version_number.desc())))


@router.post("/{prompt_id}/rollback", response_model=PromptTemplateRead, summary="回滚并创建新版本")
def rollback(prompt_id:str,data:PromptRollbackRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    prompt=accessible(db.scalar(query_with_versions().where(PromptTemplate.id==prompt_id)),user,write=True)
    source=db.scalar(select(PromptVersion).where(PromptVersion.prompt_template_id==prompt.id,PromptVersion.version_number==data.version_number))
    if not source: raise HTTPException(404,"历史版本不存在")
    next_version=max(v.version_number for v in prompt.versions)+1
    db.add(PromptVersion(prompt_template_id=prompt.id,version_number=next_version,system_prompt=source.system_prompt,user_prompt_template=source.user_prompt_template,variables_json=source.variables_json,change_note=data.change_note,created_by=user.id));db.commit()
    return db.scalar(query_with_versions().where(PromptTemplate.id==prompt.id))


@router.delete("/{prompt_id}",status_code=204,summary="删除我的 Prompt")
def delete_prompt(prompt_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    prompt=accessible(db.get(PromptTemplate,prompt_id),user,write=True)
    if prompt.owner_user_id is None: raise HTTPException(409,"系统 Prompt 不能删除")
    db.delete(prompt);db.commit();return Response(status_code=204)
