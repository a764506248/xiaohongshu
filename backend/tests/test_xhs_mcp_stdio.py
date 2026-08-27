import json

import pytest

from app.xhs_mcp import XhsMcpClient


def test_stdio_client_initializes_and_calls_tool(tmp_path):
    executable = tmp_path / "fake-xhs-mcp"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys

initialize = json.loads(sys.stdin.readline())
print(json.dumps({"jsonrpc": "2.0", "id": initialize["id"], "result": {"protocolVersion": "2025-03-26", "capabilities": {}, "serverInfo": {"name": "fake", "version": "1"}}}), flush=True)
json.loads(sys.stdin.readline())
tool = json.loads(sys.stdin.readline())
result = {"content": [{"type": "text", "text": json.dumps({"success": True, "loggedIn": True})}]}
print(json.dumps({"jsonrpc": "2.0", "id": tool["id"], "result": result}), flush=True)
""",
        encoding="utf8",
    )
    executable.chmod(0o755)

    result = XhsMcpClient(timeout=10, executable=executable).auth_status()

    payload = json.loads(result["content"][0]["text"])
    assert payload == {"success": True, "loggedIn": True}


def test_publish_rejects_embedded_mcp_failure(monkeypatch):
    client = XhsMcpClient()
    monkeypatch.setattr(client, "call_tool", lambda *args, **kwargs: {
        "content": [{"type": "text", "text": json.dumps({
            "success": False,
            "error": "BrowserError",
            "message": "Protocol error: Connection closed",
        })}],
    })

    with pytest.raises(RuntimeError, match="不能确认发布成功"):
        client.publish(title="测试", content="正文", media_paths=["unused.png"], tags=[])


def test_publish_converts_real_note_id_to_xiaohongshu_url(monkeypatch):
    client = XhsMcpClient()
    monkeypatch.setattr(client, "call_tool", lambda *args, **kwargs: {
        "content": [{"type": "text", "text": json.dumps({
            "success": True,
            "noteId": "68abcdef1234567890",
        })}],
    })

    result = client.publish(title="测试", content="正文", media_paths=["unused.png"], tags=[])

    assert result.external_id == "https://www.xiaohongshu.com/explore/68abcdef1234567890"


def test_publish_reconciles_new_matching_user_note(monkeypatch):
    client = XhsMcpClient()
    responses = iter([
        {"content": [{"type": "text", "text": json.dumps({
            "success": True,
            "data": [{"noteId": "old-note-123", "title": "旧文章"}],
        })}]},
        {"content": [{"type": "text", "text": json.dumps({"success": True})}]},
        {"content": [{"type": "text", "text": json.dumps({
            "success": True,
            "data": [
                {"noteId": "new-note-456", "title": "新文章"},
                {"noteId": "old-note-123", "title": "旧文章"},
            ],
        })}]},
    ])
    monkeypatch.setattr(client, "call_tool", lambda *args, **kwargs: next(responses))

    result = client.publish(title="新文章", content="正文", media_paths=["unused.png"], tags=["AI", "实战"])

    assert result.external_id == "https://www.xiaohongshu.com/explore/new-note-456"
