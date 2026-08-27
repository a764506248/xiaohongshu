import io
import json
import uuid
from types import SimpleNamespace

from PIL import Image


def completed_task(client):
    task = client.post("/api/v1/content-tasks", json={"title": "LangGraph 实战", "requirement": "内容克制"}).json()
    task_id = task["id"]
    client.post(f"/api/v1/content-tasks/{task_id}/generate-topics", json={})
    topic = client.get(f"/api/v1/content-tasks/{task_id}/topics").json()[0]
    client.post(f"/api/v1/content-tasks/{task_id}/select-topic", json={"topic_id": topic["id"]})
    response = client.post(
        f"/api/v1/content-tasks/{task_id}/review",
        json={"request_id": str(uuid.uuid4()), "decision": "approve"},
    )
    assert response.status_code == 200
    return task_id


def test_generate_edit_regenerate_upload_and_export_package(client):
    task_id = completed_task(client)
    response = client.post(f"/api/v1/content-tasks/{task_id}/xiaohongshu-package")
    assert response.status_code == 200, response.text
    package = response.json()
    assert 3 <= len(package["pages"]) <= 5
    assert package["tags"].startswith("#AI编程")
    first = package["pages"][0]
    assert first["versions"][0]["public_url"].startswith("/media/")

    edited = client.patch(
        f"/api/v1/image-pages/{first['id']}",
        json={"title": "新的封面标题", "body": "新的封面摘要", "template": "dark"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == "新的封面标题"
    assert len(edited.json()["versions"]) == 2

    regenerated = client.post(f"/api/v1/image-pages/{first['id']}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()["source_type"] == "regenerated"

    image = Image.new("RGB", (300, 400), "red")
    stream = io.BytesIO(); image.save(stream, "PNG"); stream.seek(0)
    uploaded = client.post(
        f"/api/v1/image-pages/{first['id']}/upload",
        files={"file": ("replacement.png", stream, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["source_type"] == "uploaded"

    saved = client.patch(
        f"/api/v1/content-tasks/{task_id}/xiaohongshu-package",
        json={"title": "最终标题", "body": "最终正文", "tags": "#AI #实战"},
    )
    assert saved.status_code == 200
    assert saved.json()["title"] == "最终标题"

    page_ids = [page["id"] for page in reversed(saved.json()["pages"])]
    reordered = client.put(
        f"/api/v1/content-tasks/{task_id}/xiaohongshu-package/page-order",
        json={"page_ids": page_ids},
    )
    assert reordered.status_code == 200, reordered.text
    assert [page["id"] for page in reordered.json()["pages"]] == page_ids

    exported = client.get(f"/api/v1/content-tasks/{task_id}/xiaohongshu-package/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    assert len(exported.content) > 1000


def test_package_requires_approved_article(client):
    task = client.post("/api/v1/content-tasks", json={"title": "未完成任务"}).json()
    response = client.post(f"/api/v1/content-tasks/{task['id']}/xiaohongshu-package")
    assert response.status_code == 409


def test_approved_article_automatically_runs_xiaohongshu_packaging_graph(client):
    task_id = completed_task(client)

    response = client.get(f"/api/v1/content-tasks/{task_id}/xiaohongshu-package")

    assert response.status_code == 200
    package = response.json()
    assert package is not None
    assert 3 <= len(package["pages"]) <= 5
    assert all(page["current_version_id"] for page in package["pages"])
    assert all(page["versions"] for page in package["pages"])


def test_get_package_returns_null_before_generation(client):
    task = client.post("/api/v1/content-tasks", json={"title": "尚未生成内容包"}).json()

    response = client.get(f"/api/v1/content-tasks/{task['id']}/xiaohongshu-package")

    assert response.status_code == 200
    assert response.json() is None


def test_get_package_keeps_404_for_missing_task(client):
    response = client.get(f"/api/v1/content-tasks/{uuid.uuid4()}/xiaohongshu-package")

    assert response.status_code == 404


def test_xhs_mcp_account_executes_approved_publish_job(client, monkeypatch):
    task_id = completed_task(client)
    package = client.post(f"/api/v1/content-tasks/{task_id}/xiaohongshu-package").json()
    variants = client.post(f"/api/v1/content-tasks/{task_id}/channel-variants").json()
    xhs_variant = next(item for item in variants if item["channel"] == "xiaohongshu")
    account = client.post("/api/v1/channel-accounts", json={
        "name": "小红书 MCP 测试账号",
        "channel": "xiaohongshu",
        "mode": "xhs_mcp",
        "credential_reference": "4141741101",
    }).json()

    calls = []

    class FakeXhsMcpClient:
        def publish(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(external_id="note-test-001", response_excerpt="published")

        def auth_status(self):
            return {"logged_in": True}

    monkeypatch.setattr("app.operations.XhsMcpClient", FakeXhsMcpClient)
    monkeypatch.setattr("app.operations_api.XhsMcpClient", FakeXhsMcpClient)

    status = client.get(f"/api/v1/channel-accounts/{account['id']}/connection-status")
    assert status.status_code == 200
    assert status.json()["status"] == "logged_in"

    job = client.post("/api/v1/publish-jobs", json={
        "channel_variant_id": xhs_variant["id"],
        "channel_account_id": account["id"],
        "idempotency_key": str(uuid.uuid4()),
        "scheduled_at": None,
        "max_retries": 1,
    }).json()
    published = client.post(f"/api/v1/publish-jobs/{job['id']}/decision", json={
        "decision": "approve",
        "comment": "测试批准",
    })
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "approved"
    assert calls == []

    published = client.post(f"/api/v1/publish-jobs/{job['id']}/execute")
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["external_post_id"] == "note-test-001"
    assert calls[0]["title"] == package["title"]
    assert len(calls[0]["media_paths"]) == len(package["pages"])

    repeated = client.post(f"/api/v1/publish-jobs/{job['id']}/decision", json={
        "decision": "reject",
        "comment": "已发布后不允许改审批结果",
    })
    assert repeated.status_code == 409


def test_xhs_mcp_status_does_not_report_browser_failure_as_logged_out(client, monkeypatch):
    account = client.post("/api/v1/channel-accounts", json={
        "name": "浏览器故障账号",
        "channel": "xiaohongshu",
        "mode": "xhs_mcp",
        "credential_reference": "",
    }).json()

    class BrokenXhsMcpClient:
        def auth_status(self):
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "error": "StatusCheckError",
                        "message": "Browser connection closed",
                    }),
                }],
            }

    monkeypatch.setattr("app.operations_api.XhsMcpClient", BrokenXhsMcpClient)
    response = client.get(f"/api/v1/channel-accounts/{account['id']}/connection-status")

    assert response.status_code == 502
    assert "StatusCheckError" in response.json()["detail"]
