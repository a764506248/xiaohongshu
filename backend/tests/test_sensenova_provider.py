from app.ai.provider import SenseNovaLLMProvider, TopicOutput


def test_article_accepts_markdown_without_json(monkeypatch):
    provider = SenseNovaLLMProvider("https://example.test/v1", "test-model", "test-key")
    markdown = "# 克制的技术标题\n\n## 核心方法\n\n正文内容。\n\n## 常见误区\n\n避免过度承诺。"
    monkeypatch.setattr(provider, "_message", lambda *args, **kwargs: markdown)

    result = provider.generate_article(TopicOutput("原始标题", "摘要", "读者", "理由", 90))

    assert result.title == "克制的技术标题"
    assert result.content == markdown
    assert result.outline == "1. 核心方法\n2. 常见误区"

