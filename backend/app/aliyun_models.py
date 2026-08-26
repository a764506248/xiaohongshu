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
]


def seed_model_configurations(db: Session) -> None:
    settings = get_settings()
    for name, provider, model, capability, protocol in CATALOG:
        if not db.scalar(select(ModelConfiguration).where(ModelConfiguration.owner_user_id.is_(None), ModelConfiguration.provider == provider, ModelConfiguration.model == model)):
            base_url = settings.openrouter_base_url if provider == "openrouter" else settings.aliyun_multimodal_base_url
            db.add(ModelConfiguration(
                name=name,
                provider=provider,
                model=model,
                capability=capability,
                protocol=protocol,
                base_url=base_url,
                enabled=True,
                is_default=model == "qwen-image-3.0-pro",
            ))
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
            "parameters": {"size": size},
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
    return db.scalar(select(ModelConfiguration).where(
        ModelConfiguration.capability == "image",
        ModelConfiguration.enabled.is_(True),
        ModelConfiguration.is_default.is_(True),
    ))
