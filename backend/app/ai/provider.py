import json
from dataclasses import asdict, dataclass

import httpx

from app.core.config import get_settings


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


class LLMProvider:
    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        raise NotImplementedError

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Deterministic local provider. Replace through the provider interface in production."""

    def generate_topics(self, title: str, requirement: str, audience: str, instruction: str = "") -> list[TopicOutput]:
        angles = [
            ("实战清单", "用清单拆解可立即执行的方法", 92),
            ("避坑指南", "总结学习和项目实践中的高频误区", 89),
            ("案例复盘", "通过完整案例呈现从问题到结果的过程", 87),
            ("工具对比", "比较常见工具的适用场景和选择标准", 84),
        ]
        return [
            TopicOutput(
                title=f"{title}：{name}",
                summary=f"围绕“{title}”{summary}。{requirement or instruction}",
                target_reader=audience,
                reason=f"{name}具有明确的信息收益，适合收藏和转发。",
                score=float(score),
            )
            for name, summary, score in angles
        ]

    def generate_article(self, topic: TopicOutput, instruction: str = "") -> ArticleOutput:
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
        return ArticleOutput(title=topic.title, outline=outline, content=content)


class OpenRouterLLMProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 120):
        if not api_key:
            raise RuntimeError("OpenRouter LLM_API_KEY 未配置")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def _structured(self, system: str, user: str, schema_name: str, schema: dict):
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
        message = response.json()["choices"][0]["message"]["content"]
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
        )
        return ArticleOutput(**data)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openrouter":
        return OpenRouterLLMProvider(
            settings.llm_base_url, settings.llm_model, settings.llm_api_key, settings.llm_timeout_seconds
        )
    raise RuntimeError(f"不支持的 LLM_PROVIDER：{settings.llm_provider}")
