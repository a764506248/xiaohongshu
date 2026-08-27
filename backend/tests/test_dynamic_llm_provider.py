from types import SimpleNamespace

import httpx
import pytest

from app.ai.provider import (
    FallbackLLMProvider,
    LLMProvider,
    MockLLMProvider,
    OpenRouterLLMProvider,
    SenseNovaLLMProvider,
    provider_from_model_configuration,
)


def response(payload: dict, method: str = "POST", url: str = "https://llm.example/v1") -> httpx.Response:
    return httpx.Response(200, json=payload, request=httpx.Request(method, url))


def test_openai_compatible_topics_request_and_usage(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return response({
            "choices": [{"message": {"content": '{"topics":[{"title":"动态模型","summary":"摘要","target_reader":"开发者","reason":"实用","score":91}]}'}}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 13},
        }, url=url)

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenRouterLLMProvider("https://llm.example/v1/", "vendor/model-a", "secret-a", 33, "custom-openai")
    topics = provider.generate_topics("LangGraph", "实战", "开发者")

    assert topics[0].title == "动态模型"
    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-a"
    assert captured["json"]["model"] == "vendor/model-a"
    assert captured["json"]["response_format"]["type"] == "json_schema"
    assert captured["timeout"] == 33
    usage = provider.consume_usage()
    assert (usage.provider, usage.model, usage.input_tokens, usage.output_tokens) == (
        "custom-openai", "vendor/model-a", 21, 13
    )


def test_anthropic_compatible_article_request_and_usage(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return response({
            "content": [{"type": "text", "text": "# 测试文章\n\n## 步骤\n\n正文"}],
            "usage": {"input_tokens": 18, "output_tokens": 9},
        }, url=url)

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = SenseNovaLLMProvider("https://anthropic.example/v1/", "deepseek-v4-flash", "secret-b", 44, "custom-anthropic")
    from app.ai.provider import TopicOutput
    article = provider.generate_article(TopicOutput("原题", "摘要", "读者", "原因", 90))

    assert article.title == "测试文章"
    assert captured["url"] == "https://anthropic.example/v1/messages"
    assert captured["headers"]["Authorization"] == "Bearer secret-b"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["model"] == "deepseek-v4-flash"
    assert captured["json"]["max_tokens"] == 8192
    assert captured["timeout"] == 44
    usage = provider.consume_usage()
    assert (usage.provider, usage.model, usage.input_tokens, usage.output_tokens) == (
        "custom-anthropic", "deepseek-v4-flash", 18, 9
    )


@pytest.mark.parametrize(
    ("protocol", "expected_type"),
    [("openai_compatible", OpenRouterLLMProvider), ("anthropic_compatible", SenseNovaLLMProvider)],
)
def test_database_model_configuration_selects_matching_adapter(protocol, expected_type):
    model = SimpleNamespace(
        enabled=True,
        capability="text",
        protocol=protocol,
        provider="my-provider",
        model="my-model",
        base_url="https://model.example/v1",
        api_key="database-key",
    )
    provider = provider_from_model_configuration(model)
    assert isinstance(provider, expected_type)
    assert provider.model == "my-model"
    assert provider.api_key == "database-key"


def test_database_model_configuration_rejects_unsupported_or_disabled_model():
    disabled = SimpleNamespace(enabled=False, capability="text", protocol="openai_compatible")
    with pytest.raises(RuntimeError, match="已停用"):
        provider_from_model_configuration(disabled)

    unsupported = SimpleNamespace(enabled=True, capability="text", protocol="dashscope_native")
    with pytest.raises(RuntimeError, match="暂不支持"):
        provider_from_model_configuration(unsupported)


def test_fallback_provider_switches_on_429_and_records_successful_usage():
    class LimitedProvider(LLMProvider):
        model = "limited-model"
        provider_name = "limited"

        def generate_topics(self, *args, **kwargs):
            request = httpx.Request("POST", "https://limited.example/chat/completions")
            raise httpx.HTTPStatusError("429 Too Many Requests", request=request, response=httpx.Response(429, request=request))

    class AvailableProvider(MockLLMProvider):
        model = "aliyun-fallback"
        provider_name = "aliyun_token_plan"

    provider = FallbackLLMProvider([LimitedProvider(), AvailableProvider()])
    topics = provider.generate_topics("主题", "要求", "读者")
    assert topics
    usage = provider.consume_usage()
    assert usage is not None
    assert usage.provider == "mock"


def test_fallback_provider_does_not_hide_non_retryable_parsing_error():
    class InvalidProvider(LLMProvider):
        model = "invalid-model"

        def generate_article(self, *args, **kwargs):
            raise RuntimeError("响应 JSON 格式错误")

    class ShouldNotRun(LLMProvider):
        def generate_article(self, *args, **kwargs):
            raise AssertionError("非重试错误不应触发兜底")

    provider = FallbackLLMProvider([InvalidProvider(), ShouldNotRun()])
    from app.ai.provider import TopicOutput
    with pytest.raises(RuntimeError, match="JSON 格式错误"):
        provider.generate_article(TopicOutput("题目", "摘要", "读者", "原因", 90))


def test_langgraph_uses_task_selected_model_for_topics_and_article(client, monkeypatch):
    calls: list[str] = []

    class TrackingProvider(MockLLMProvider):
        def generate_topics(self, *args, **kwargs):
            calls.append("generate_topics")
            return super().generate_topics(*args, **kwargs)

        def generate_article(self, *args, **kwargs):
            calls.append("generate_article")
            return super().generate_article(*args, **kwargs)

    monkeypatch.setattr(
        "app.workflows.content_creation.graph.provider_from_model_configuration",
        lambda model: TrackingProvider(),
    )
    configured = client.post("/api/v1/models", json={
        "name": "工作流动态模型",
        "provider": "test-provider",
        "model": "test-dynamic-model",
        "capability": "text",
        "protocol": "openai_compatible",
        "base_url": "https://model.example/v1",
        "api_key": "test-key",
        "enabled": True,
    })
    assert configured.status_code == 201, configured.text
    model_id = configured.json()["id"]

    created = client.post("/api/v1/content-tasks", json={
        "title": "动态模型工作流",
        "requirement": "验证选择",
        "target_audience": "开发者",
        "model_configuration_id": model_id,
    })
    assert created.status_code == 201, created.text
    assert created.json()["model_configuration_id"] == model_id
    task_id = created.json()["id"]

    generated = client.post(f"/api/v1/content-tasks/{task_id}/generate-topics", json={})
    assert generated.status_code == 200, generated.text
    topic_id = client.get(f"/api/v1/content-tasks/{task_id}/topics").json()[0]["id"]
    selected = client.post(f"/api/v1/content-tasks/{task_id}/select-topic", json={"topic_id": topic_id})
    assert selected.status_code == 200, selected.text
    assert calls == ["generate_topics", "generate_article"]
