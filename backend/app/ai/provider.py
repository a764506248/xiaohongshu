import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass

import httpx
from langsmith import traceable

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TopicOutput:
    title: str
    summary: str
    target_reader: str
    reason: str
    score: float


@dataclass
class ArticleOutput:
    title: str
    outline: str
    content: str


@dataclass
class UsageRecord:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    status: str = "success"


class LLMProvider:
    _usage = threading.local()

    def _set_usage(self, usage: UsageRecord) -> None:
        self._usage.value = usage

    def consume_usage(self) -> UsageRecord | None:
        usage = getattr(self._usage, "value", None)
        self._usage.value = None
        return usage

    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        raise NotImplementedError

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
        raise NotImplementedError


def is_retryable_model_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {402, 408, 429, 500, 502, 503, 504}
    text = str(exc).lower()
    return any(marker in text for marker in (
        "http 402", "http 408", "http 429", "http 500", "http 502", "http 503", "http 504",
        "too many requests", "rate_limit", "rate limit", "quota exceeded", "allocated quota",
        "timed out", "timeout",
    ))


class FallbackLLMProvider(LLMProvider):
    """按顺序调用文本模型，仅在限流、额度或临时服务错误时切换。"""

    def __init__(self, providers: list[LLMProvider]):
        if not providers:
            raise RuntimeError("没有可用的文本模型")
        self.providers = providers
        self.active: LLMProvider | None = None

    def _call(self, method: str, *args, **kwargs):
        failures: list[str] = []
        for index, provider in enumerate(self.providers):
            try:
                result = getattr(provider, method)(*args, **kwargs)
                self.active = provider
                if index:
                    logger.warning("llm_fallback.succeeded method=%s fallback_index=%d provider=%s model=%s", method, index, getattr(provider, "provider_name", "unknown"), getattr(provider, "model", "unknown"))
                return result
            except Exception as exc:
                failures.append(f"{getattr(provider, 'model', provider.__class__.__name__)}: {exc}")
                if not is_retryable_model_error(exc) or index == len(self.providers) - 1:
                    raise RuntimeError("模型调用失败；" + "；".join(failures)) from exc
                logger.warning("llm_fallback.retry method=%s provider=%s model=%s reason=%s", method, getattr(provider, "provider_name", "unknown"), getattr(provider, "model", "unknown"), str(exc)[:200])
        raise RuntimeError("所有文本模型均不可用")

    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        return self._call("generate_topics", title, requirement, audience, instruction)

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
        return self._call("generate_article", topic, instruction)

    def consume_usage(self) -> UsageRecord | None:
        return self.active.consume_usage() if self.active else None


class MockLLMProvider(LLMProvider):
    """Deterministic local provider. Replace through the provider interface in production."""

    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        started = time.perf_counter()
        angles = [
            ("实战清单", "用清单拆解可立即执行的方法", 92),
            ("避坑指南", "总结学习和项目实践中的高频误区", 89),
            ("案例复盘", "通过完整案例呈现从问题到结果的过程", 87),
            ("工具对比", "比较常见工具的适用场景和选择标准", 84),
        ]
        result = [
            TopicOutput(
                title=f"{title}：{name}",
                summary=f"围绕“{title}”{summary}。{requirement or instruction}",
                target_reader=audience,
                reason=f"{name}具有明确的信息收益，适合收藏和转发。",
                score=float(score),
            )
            for name, summary, score in angles
        ]
        self._set_usage(UsageRecord("mock", "mock-local", max(1, len(f"{title}{requirement}{audience}{instruction}") // 4), max(1, len(str(result)) // 4), int((time.perf_counter() - started) * 1000)))
        return result

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
        started = time.perf_counter()
        outline = "一、为什么值得关注\n二、核心方法\n三、实践步骤\n四、常见误区\n五、行动建议"
        content = (
            f"# {topic.title}\n\n"
            f"{topic.summary}\n\n"
            "## 为什么值得关注\n\nAI 应用开发的关键不是堆叠工具，而是把真实问题拆成可以验证的步骤。\n\n"
            "## 核心方法\n\n先明确目标用户和预期结果，再设计最小流程，通过结构化输出和人工审核提高稳定性。\n\n"
            "## 实践步骤\n\n1. 选择一个明确场景。\n2. 定义输入与输出。\n3. 建立可重复测试。\n4. 保存每次迭代结果。\n\n"
            "## 常见误区\n\n不要把模型输出直接等同于最终成果。重要内容需要事实检查、版本管理和人工确认。\n\n"
            "## 行动建议\n\n从一个每天都会发生的小任务开始，用一周时间完成第一个可用闭环。"
        )
        if instruction:
            content += f"\n\n> 本次修订要求：{instruction}"
        result = ArticleOutput(title=topic.title, outline=outline, content=content)
        self._set_usage(UsageRecord("mock", "mock-local", max(1, len(f"{topic}{instruction}") // 4), max(1, len(content) // 4), int((time.perf_counter() - started) * 1000)))
        return result


class OpenRouterLLMProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 120, provider_name: str = "openrouter"):
        if not api_key:
            raise RuntimeError("OpenRouter LLM_API_KEY 未配置")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.provider_name = provider_name

    @traceable(name="openai-compatible-llm", run_type="llm")
    def _structured(self, system: str, user: str, schema_name: str, schema: dict):
        started = time.perf_counter()
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.7,
                "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        self._set_usage(UsageRecord(self.provider_name, self.model, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)), int((time.perf_counter() - started) * 1000)))
        if isinstance(message, list):
            message = "".join(part.get("text", "") for part in message if isinstance(part, dict))
        return json.loads(message)

    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        schema = {
            "type": "object",
            "properties": {"topics": {"type": "array", "minItems": 4, "maxItems": 6, "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"}, "summary": {"type": "string"},
                    "target_reader": {"type": "string"}, "reason": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["title", "summary", "target_reader", "reason", "score"], "additionalProperties": False,
            }}},
            "required": ["topics"], "additionalProperties": False,
        }
        data = self._structured(
            "你是教育培训公司的中文内容运营专家。请生成有技术含量、避免夸张承诺的候选选题。",
            f"内容方向：{title}\n目标受众：{audience}\n基础要求：{requirement}\n补充要求：{instruction}",
            "topic_candidates", schema,
            langsmith_extra={"metadata": {"ls_provider": self.provider_name, "ls_model_name": self.model}},
        )
        return [TopicOutput(**item) for item in data["topics"]]

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
        schema = {
            "type": "object",
            "properties": {"title": {"type": "string"}, "outline": {"type": "string"}, "content": {"type": "string"}},
            "required": ["title", "outline", "content"], "additionalProperties": False,
        }
        data = self._structured(
            "你是 AI 应用开发培训领域的中文技术作者。文章必须准确、实用、结构清晰，正文使用 Markdown。",
            f"选题信息：{json.dumps(asdict(topic), ensure_ascii=False)}\n修订要求：{instruction}",
            "article", schema,
            langsmith_extra={"metadata": {"ls_provider": self.provider_name, "ls_model_name": self.model}},
        )
        return ArticleOutput(**data)


class SenseNovaLLMProvider(LLMProvider):
    """Anthropic Messages compatible adapter for token.sensenova.cn."""

    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 120, provider_name: str = "sensenova"):
        if not api_key:
            raise RuntimeError("SenseNova LLM_API_KEY 未配置")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.provider_name = provider_name

    @traceable(name="anthropic-compatible-llm", run_type="llm")
    def _message(self, system: str, user: str, max_tokens: int = 4096) -> str:
        started = time.perf_counter()
        response = httpx.post(
            f"{self.base_url}/messages",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=self.timeout,
        )
        if response.is_error:
            detail = response.text[:500]
            raise RuntimeError(f"SenseNova 请求失败（HTTP {response.status_code}）：{detail}")
        payload = response.json()
        blocks = payload.get("content", [])
        usage = payload.get("usage", {})
        self._set_usage(UsageRecord(self.provider_name, self.model, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)), int((time.perf_counter() - started) * 1000)))
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        if not text:
            raise RuntimeError("SenseNova 响应中没有文本内容")
        return text

    @staticmethod
    def _parse_json(text: str) -> dict:
        cleaned = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)
        else:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start >= 0 and end > start:
                cleaned = cleaned[start:end + 1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("SenseNova 未返回有效 JSON") from exc

    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        text = self._message(
            "你是教育培训公司的中文内容运营专家。只输出合法 JSON，不要 Markdown 代码块。",
            "请生成4个有技术含量、避免夸张承诺的候选选题。JSON格式必须为："
            '{"topics":[{"title":"", "summary":"", "target_reader":"", "reason":"", "score":90}]}。'
            f"\n内容方向：{title}\n目标受众：{audience}\n基础要求：{requirement}\n补充要求：{instruction}",
            langsmith_extra={"metadata": {"ls_provider": self.provider_name, "ls_model_name": self.model}},
        )
        data = self._parse_json(text)
        topics = data.get("topics")
        if not isinstance(topics, list) or not topics:
            raise RuntimeError("SenseNova 返回的选题列表为空")
        return [TopicOutput(**item) for item in topics]

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
        text = self._message(
            "你是 AI 应用开发培训领域的中文技术作者。直接输出完整 Markdown 文章，不要输出 JSON，不要使用代码块包裹整篇文章。",
            "请生成准确、实用、结构清晰且措辞克制的中文技术文章。"
            "正文需要包含清晰的二级标题、实践步骤和常见误区，避免夸张承诺。"
            f"\n选题信息：{json.dumps(asdict(topic), ensure_ascii=False)}\n修订要求：{instruction}",
            max_tokens=8192,
            langsmith_extra={"metadata": {"ls_provider": self.provider_name, "ls_model_name": self.model}},
        )
        content = text.strip()
        headings = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
        outline = "\n".join(f"{index + 1}. {heading.strip()}" for index, heading in enumerate(headings))
        if not outline:
            outline = "1. 背景与问题\n2. 核心方法\n3. 实践步骤\n4. 常见误区\n5. 行动建议"
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        article_title = title_match.group(1).strip() if title_match else topic.title
        return ArticleOutput(title=article_title, outline=outline, content=content)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openrouter":
        return OpenRouterLLMProvider(
            settings.llm_base_url, settings.llm_model, settings.llm_api_key, settings.llm_timeout_seconds
        )
    if settings.llm_provider == "sensenova":
        return SenseNovaLLMProvider(
            settings.llm_base_url, settings.llm_model, settings.llm_api_key, settings.llm_timeout_seconds
        )
    raise RuntimeError(f"不支持的 LLM_PROVIDER：{settings.llm_provider}")


def provider_from_model_configuration(model) -> LLMProvider:
    """把模型管理表中的一行配置转换成内容工作流使用的统一适配器。"""
    settings = get_settings()
    if not model.enabled or model.capability != "text":
        raise RuntimeError("任务选择的文本模型已停用或不可用")
    if model.protocol == "openai_compatible":
        key = model.api_key or (settings.openrouter_model_api_key if model.provider == "openrouter" else "")
        return OpenRouterLLMProvider(model.base_url, model.model, key, settings.llm_timeout_seconds, model.provider)
    if model.protocol == "anthropic_compatible":
        key = model.api_key or (settings.llm_api_key if model.provider == settings.llm_provider else "")
        return SenseNovaLLMProvider(model.base_url, model.model, key, settings.llm_timeout_seconds, model.provider)
    raise RuntimeError(f"文本模型协议暂不支持内容生成：{model.protocol}")
