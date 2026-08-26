from fastapi import HTTPException

from app.auth import require_permission
from app.models import User


def test_user_management_and_permission_assignment(client):
    created = client.post("/api/v1/users", json={
        "username": "publisher", "display_name": "发布运营", "password": "secret123",
        "role": "operator", "permission_codes": ["content:view", "publish:view", "publish:execute"],
    })
    assert created.status_code == 201, created.text
    user = created.json()
    assert "publish:execute" in user["permission_codes"]

    updated = client.put(f"/api/v1/users/{user['id']}", json={
        "display_name": "发布审核员", "role": "operator", "status": "active",
        "permission_codes": ["publish:view", "publish:approve"],
    })
    assert updated.status_code == 200
    assert updated.json()["permission_codes"] == ["publish:approve", "publish:view"]
    assert client.post(f"/api/v1/users/{user['id']}/reset-password", json={"password": "newpass123"}).status_code == 200


def test_permission_dependency_rejects_operator_without_permission():
    operator = User(username="reader", display_name="只读用户", password_hash="", role="operator", permissions_csv="publish:view")
    dependency = require_permission("publish:execute")
    try:
        dependency(operator)
        assert False, "missing permission should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 403
