import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ModelConfiguration

CATALOG = [
    ("万相 2.7 图片旗舰版", "aliyun_token_plan", "wan2.7-image-pro", "image", "dashscope_native"),
    ("千问 Image 3.0 Pro", "aliyun_token_plan", "qwen-image-3.0-pro", "image", "dashscope_native"),
    ("HappyHorse 1.1 图生视频", "aliyun_token_plan", "happyhorse-1.1-i2v", "image_to_video", "dashscope_native"),
    ("OpenRouter Stealth Ox Alpha", "openrouter", "stealth/ox-alpha", "text", "openai_compatible"),
    ("SenseNova DeepSeek V4 Flash", "sensenova", "deepseek-v4-flash", "text", "anthropic_compatible"),
    ("阿里 DeepSeek V4 Flash 0731", "aliyun_token_plan", "deepseek-v4-flash-0731", "text", "openai_compatible"),
]


def seed_model_configurations(db: Session) -> None:
    settings = get_settings()
    for name, provider, model, capability, protocol in CATALOG:
        configured = db.scalar(select(ModelConfiguration).where(
            ModelConfiguration.owner_user_id.is_(None),
            ModelConfiguration.provider == provider,
            ModelConfiguration.model == model,
        ))
        if provider == "openrouter":
            base_url, api_key = settings.openrouter_base_url, settings.openrouter_model_api_key
        elif provider == "sensenova":
            base_url, api_key = settings.llm_base_url, settings.llm_api_key
        elif capability == "text":
            base_url, api_key = settings.aliyun_openai_base_url, settings.aliyun_model_api_key
        else:
            base_url, api_key = settings.aliyun_multimodal_base_url, settings.aliyun_model_api_key
        if not configured:
            db.add(ModelConfiguration(
                name=name,
                provider=provider,
                model=model,
                capability=capability,
                protocol=protocol,
                base_url=base_url,
                api_key=api_key or None,
                enabled=True,
                is_default=model in {"qwen-image-3.0-pro", "deepseek-v4-flash"},
            ))
        else:
            # 旧版本仅从 .env 读取系统密钥，数据库字段可能为空。
            # 只补空值，避免启动时覆盖后台已经修改过的数据库密钥。
            if not configured.api_key and api_key:
                configured.api_key = api_key
            # 系统预置地址由环境配置维护，允许部署环境切换区域端点。
            configured.base_url = base_url
    db.commit()


def generate_image(model: ModelConfiguration, prompt: str, size: str = "1024*1365", api_key: str | None = None) -> tuple[bytes, str, int]:
    settings = get_settings()
    key = api_key or settings.aliyun_model_api_key
    if not key:
        raise RuntimeError("ALIYUN_MODEL_API_KEY 未配置")
    if model.capability != "image":
        raise ValueError("该模型需要输入图片，暂不能用于文生图测试")
    started = time.perf_counter()
    response = httpx.post(
        f"{model.base_url.rstrip('/')}/services/aigc/multimodal-generation/generation",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model.model,
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {
                "size": size,
                "n": 1,
                "watermark": False,
            },
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    contents = payload.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", [])
    output_url = next((item.get("image") for item in contents if item.get("image")), None)
    if not output_url:
        raise RuntimeError(f"模型未返回图片：{payload.get('message') or payload.get('code') or '未知响应'}")
    image_response = httpx.get(output_url, timeout=120)
    image_response.raise_for_status()
    return image_response.content, output_url, int((time.perf_counter() - started) * 1000)


def generate_text(model: ModelConfiguration, prompt: str, api_key: str | None = None) -> tuple[str, int]:
    settings = get_settings()
    key = api_key or settings.openrouter_model_api_key
    if not key:
        raise RuntimeError("OPENROUTER_MODEL_API_KEY 未配置")
    if model.capability != "text":
        raise ValueError("该模型不是文本生成模型")
    started = time.perf_counter()
    response = httpx.post(
        f"{model.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 80},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("模型未返回文本内容")
    return content, int((time.perf_counter() - started) * 1000)


def default_image_model(db: Session) -> ModelConfiguration | None:
    # 内容图片只能使用阿里 Token Plan 图片模型。优先使用后台指定的默认模型；
    # 如果默认项被停用，则回退到任一启用的阿里图片模型，而不是回退到本地占位图。
    return db.scalar(
        select(ModelConfiguration)
        .where(
            ModelConfiguration.provider == "aliyun_token_plan",
            ModelConfiguration.capability == "image",
            ModelConfiguration.enabled.is_(True),
        )
        .order_by(
            ModelConfiguration.is_default.desc(),
            # qwen-image-3.0-pro 更适合知识卡片中的中英文文字渲染。
            (ModelConfiguration.model == "qwen-image-3.0-pro").desc(),
            ModelConfiguration.created_at.asc(),
        )
    )
