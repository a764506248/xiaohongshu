import uuid


def create_task(client):
    response = client.post(
        "/api/v1/content-tasks",
        json={"title": "LangGraph 入门", "requirement": "适合零基础", "target_audience": "AI 应用开发初学者"},
    )
    assert response.status_code == 201
    return response.json()


def test_health_and_task_crud(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.headers["x-request-id"]

    task = create_task(client)
    assert task["status"] == "draft"
    assert client.get(f"/api/v1/content-tasks/{task['id']}").status_code == 200
    listing = client.get("/api/v1/content-tasks").json()
    assert [item["id"] for item in listing] == [task["id"]]

    updated = client.patch(f"/api/v1/content-tasks/{task['id']}", json={"requirement": "强调实战"})
    assert updated.status_code == 200
    assert updated.json()["requirement"] == "强调实战"


def test_full_content_workflow_with_rejection_and_idempotent_review(client):
    task = create_task(client)
    task_id = task["id"]

    generated = client.post(f"/api/v1/content-tasks/{task_id}/generate-topics", json={"instruction": "给出四个角度"})
    assert generated.status_code == 200, generated.text
    assert generated.json()["status"] == "waiting_topic_selection"

    topics = client.get(f"/api/v1/content-tasks/{task_id}/topics").json()
    assert len(topics) == 4
    assert topics[0]["score"] >= topics[-1]["score"]

    selected = client.post(f"/api/v1/content-tasks/{task_id}/select-topic", json={"topic_id": topics[0]["id"]})
    assert selected.status_code == 200, selected.text

    task_state = client.get(f"/api/v1/content-tasks/{task_id}").json()
    assert task_state["status"] == "waiting_article_review"
    article = client.get(f"/api/v1/content-tasks/{task_id}/article").json()
    assert len(article["versions"]) == 1
    assert article["versions"][0]["source_type"] == "ai_generated"
    usage = client.get("/api/v1/analytics/model-usage").json()
    assert [item["operation"] for item in usage] == ["generate_article", "generate_topics"]
    assert all(item["input_tokens"] > 0 and item["output_tokens"] > 0 for item in usage)
    summary = client.get("/api/v1/analytics/summary").json()
    assert summary["model_calls"] == 2
    assert summary["total_tokens"] == summary["total_input_tokens"] + summary["total_output_tokens"]
    report = client.get("/api/v1/analytics/token-usage", params={"start_at": "2000-01-01T00:00:00", "end_at": "2100-01-01T00:00:00", "granularity": "month"}).json()
    assert report["calls"] == 2
    assert report["total_tokens"] == summary["total_tokens"]
    assert len(report["points"]) == 1

    request_id = str(uuid.uuid4())
    rejected = client.post(
        f"/api/v1/content-tasks/{task_id}/review",
        json={"request_id": request_id, "decision": "reject", "comment": "增加更多实战步骤"},
    )
    assert rejected.status_code == 200, rejected.text
    revised = client.get(f"/api/v1/content-tasks/{task_id}/article").json()
    assert len(revised["versions"]) == 2
    assert revised["versions"][1]["source_type"] == "ai_revised"
    assert "增加更多实战步骤" in revised["versions"][1]["content"]
    assert client.get("/api/v1/analytics/summary").json()["model_calls"] == 3

    duplicate = client.post(
        f"/api/v1/content-tasks/{task_id}/review",
        json={"request_id": request_id, "decision": "reject", "comment": "增加更多实战步骤"},
    )
    assert duplicate.status_code == 200
    assert len(client.get(f"/api/v1/content-tasks/{task_id}/reviews").json()) == 1
    assert len(client.get(f"/api/v1/content-tasks/{task_id}/article").json()["versions"]) == 2

    approved = client.post(
        f"/api/v1/content-tasks/{task_id}/review",
        json={"request_id": str(uuid.uuid4()), "decision": "approve", "comment": "通过"},
    )
    assert approved.status_code == 200, approved.text
    assert client.get(f"/api/v1/content-tasks/{task_id}").json()["status"] == "completed"


def test_edit_and_approve_creates_human_version(client):
    task = create_task(client)
    task_id = task["id"]
    client.post(f"/api/v1/content-tasks/{task_id}/generate-topics", json={})
    topic = client.get(f"/api/v1/content-tasks/{task_id}/topics").json()[0]
    client.post(f"/api/v1/content-tasks/{task_id}/select-topic", json={"topic_id": topic["id"]})

    response = client.post(
        f"/api/v1/content-tasks/{task_id}/review",
        json={
            "request_id": str(uuid.uuid4()),
            "decision": "edit_and_approve",
            "edited_title": "人工确认标题",
            "edited_content": "这是人工确认后的最终正文。",
        },
    )
    assert response.status_code == 200, response.text
    article = client.get(f"/api/v1/content-tasks/{task_id}/article").json()
    assert article["versions"][-1]["source_type"] == "human_edited"
    assert article["versions"][-1]["title"] == "人工确认标题"
    assert client.get(f"/api/v1/content-tasks/{task_id}").json()["status"] == "completed"


def test_invalid_state_is_rejected(client):
    task = create_task(client)
    response = client.post(f"/api/v1/content-tasks/{task['id']}/select-topic", json={"topic_id": "missing"})
    assert response.status_code == 409


def test_topic_subgraph_combines_configured_llm_and_rag_candidates(client):
    history = create_task(client)
    response = client.post(
        f"/api/v1/content-tasks/{history['id']}/generate-topics",
        json={"llm_topic_count": 4, "rag_topic_count": 0},
    )
    assert response.status_code == 200, response.text

    current = client.post(
        "/api/v1/content-tasks",
        json={"title": "LangGraph 进阶", "requirement": "强调工程实践", "target_audience": "后端工程师"},
    ).json()
    response = client.post(
        f"/api/v1/content-tasks/{current['id']}/generate-topics",
        json={"llm_topic_count": 2, "rag_topic_count": 2},
    )
    assert response.status_code == 200, response.text

    topics = client.get(f"/api/v1/content-tasks/{current['id']}/topics").json()
    assert len(topics) == 4
    assert sum(topic["reason"].startswith("RAG 历史召回") for topic in topics) == 2


def test_streaming_topic_and_article_workflow(client):
    task = create_task(client)
    generated = client.post(
        f"/api/v1/content-tasks/{task['id']}/generate-topics/stream",
        json={"llm_topic_count": 2, "rag_topic_count": 0},
    )
    assert generated.status_code == 200
    assert "event: started" in generated.text
    assert "generate_llm_topics" in generated.text
    assert "event: completed" in generated.text

    topic = client.get(f"/api/v1/content-tasks/{task['id']}/topics").json()[0]
    article = client.post(
        f"/api/v1/content-tasks/{task['id']}/select-topic/stream",
        json={"topic_id": topic["id"]},
    )
    assert article.status_code == 200
    assert "generate_article" in article.text
    assert "event: completed" in article.text
    assert client.get(f"/api/v1/content-tasks/{task['id']}").json()["status"] == "waiting_article_review"
