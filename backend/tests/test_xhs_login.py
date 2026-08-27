import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import xhs_login


def test_login_session_is_pollable_immediately(tmp_path, monkeypatch):
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    login_root = tmp_path / "sessions"
    monkeypatch.setattr(xhs_login, "NODE_MODULES", node_modules)
    monkeypatch.setattr(xhs_login, "LOGIN_ROOT", login_root)
    monkeypatch.setattr(xhs_login.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(pid=123))

    created = xhs_login.start_login_session()
    status = xhs_login.login_session_status(created["session_id"])

    assert status["status"] == "starting"
    assert status["message"] == "正在生成登录二维码"
    stored = json.loads((login_root / created["session_id"] / "status.json").read_text("utf8"))
    assert stored["status"] == "starting"


def test_missing_login_session_still_returns_404(tmp_path, monkeypatch):
    monkeypatch.setattr(xhs_login, "LOGIN_ROOT", tmp_path)

    with pytest.raises(HTTPException) as error:
        xhs_login.login_session_status("a014d825-b9b7-421d-b99e-3cfc8b9725db")

    assert error.value.status_code == 404
