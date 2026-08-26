import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import PromptTemplate, PromptVersion

SYSTEM_PROMPTS = [
    ("候选选题生成", "content.generate_topics", ["内容", "选题", "LLM"], "topic_generation", "text", "你是资深技术内容策划。", "围绕 {{ title }}，面向 {{ audience }}，生成 {{ count }} 个技术选题。补充要求：{{ instruction }}", ["title","audience","count","instruction"]),
    ("技术文章生成", "content.generate_article", ["内容", "文章", "LLM"], "article_generation", "text", "你是技术教育内容作者。", "根据选题 {{ topic }} 生成结构清晰、可执行的文章。修改要求：{{ instruction }}", ["topic","instruction"]),
    ("知识卡片图片", "media.generate_image", ["图片", "小红书", "知识卡片"], "image_generation", "image", "", "生成竖版知识卡片。标题：{{ title }}；正文：{{ body }}；视觉要求：{{ visual_description }}", ["title","body","visual_description"]),
]


def seed_system_prompts(db: Session) -> None:
    for name,key,tags,scene,capability,system,user_template,variables in SYSTEM_PROMPTS:
        if db.scalar(select(PromptTemplate).where(PromptTemplate.owner_user_id.is_(None),PromptTemplate.prompt_key==key)): continue
        prompt=PromptTemplate(name=name,prompt_key=key,tags_csv=",".join(tags),scene=scene,model_capability=capability,description="系统预置 Prompt，可复制为个人版本",status="enabled",is_default=True)
        db.add(prompt);db.flush();db.add(PromptVersion(prompt_template_id=prompt.id,version_number=1,system_prompt=system,user_prompt_template=user_template,variables_json=json.dumps(variables,ensure_ascii=False),change_note="系统初始版本"))
    db.commit()


def resolve_prompt(db:Session,prompt_key:str,owner_user_id:str|None=None)->PromptTemplate|None:
    """后续工作流节点按稳定 prompt_key 获取个人默认项，并回退到系统默认项。"""
    prompts=list(db.scalars(select(PromptTemplate).options(selectinload(PromptTemplate.versions)).where(PromptTemplate.prompt_key==prompt_key,PromptTemplate.status=="enabled",PromptTemplate.is_default.is_(True))))
    return next((p for p in prompts if p.owner_user_id==owner_user_id),None) or next((p for p in prompts if p.owner_user_id is None),None)
