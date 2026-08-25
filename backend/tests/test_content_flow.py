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

