import io
import uuid

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

