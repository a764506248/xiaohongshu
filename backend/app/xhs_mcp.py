import json
import os
import queue
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
XHS_MCP_EXECUTABLE = PROJECT_ROOT / "xhs-login" / "node_modules" / ".bin" / "xhs-mcp"


@dataclass
class XhsPublishResult:
    external_id: str
    response_excerpt: str


class XhsMcpClient:
    """通过本机 stdio 子进程调用 xhs-mcp，不开放任何网络监听端口。"""

    def __init__(self, timeout: float | None = None, executable: Path | None = None):
        settings = get_settings()
        self.timeout = timeout or settings.xhs_mcp_timeout_seconds
        self.executable = executable or XHS_MCP_EXECUTABLE

    @staticmethod
    def _send(process: subprocess.Popen, body: dict) -> None:
        if process.stdin is None:
            raise RuntimeError("XHS MCP 标准输入不可用")
        process.stdin.write(json.dumps(body, ensure_ascii=False) + "\n")
        process.stdin.flush()

    def _receive(self, process: subprocess.Popen, request_id: str) -> dict:
        if process.stdout is None:
            raise RuntimeError("XHS MCP 标准输出不可用")
        while True:
            lines: queue.Queue[str] = queue.Queue(maxsize=1)
            threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
            try:
                line = lines.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise TimeoutError(f"XHS MCP 调用超过 {self.timeout:g} 秒") from exc
            if not line:
                code = process.poll()
                raise RuntimeError(f"XHS MCP 子进程异常退出（退出码 {code}）")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(payload.get("id")) != request_id:
                continue
            if payload.get("error"):
                error = payload["error"]
                raise RuntimeError(error.get("message", str(error)))
            return payload

    def call_tool(self, name: str, arguments: dict) -> dict:
        if not self.executable.is_file():
            raise RuntimeError("XHS MCP 尚未安装，请执行 cd xhs-login && npm install")
        environment = os.environ.copy()
        environment["XHS_ENABLE_LOGGING"] = "false"
        # 即使宿主机环境配置了 XHS_HEADLESS=false，后台发布也不得弹出浏览器窗口。
        environment["XHS_HEADLESS"] = "true"
        process = subprocess.Popen(
            [str(self.executable), "mcp", "--mode", "stdio"],
            cwd=PROJECT_ROOT / "xhs-login",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=environment,
        )
        try:
            initialize_id = str(uuid.uuid4())
            self._send(process, {
                "jsonrpc": "2.0",
                "id": initialize_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "xiaohongshu-operator", "version": "1.0.0"},
                },
            })
            initialized = self._receive(process, initialize_id)
            if not initialized.get("result"):
                raise RuntimeError("XHS MCP 初始化失败")
            self._send(process, {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            })
            tool_id = str(uuid.uuid4())
            self._send(process, {
                "jsonrpc": "2.0",
                "id": tool_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            })
            payload = self._receive(process, tool_id)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        result = payload.get("result", {})
        if result.get("isError"):
            text = " ".join(item.get("text", "") for item in result.get("content", []))
            raise RuntimeError(text or "XHS MCP 工具执行失败")
        embedded = self._embedded_result(result)
        if embedded and embedded.get("success") is False:
            error_name = embedded.get("error", "XHS MCP 工具执行失败")
            error_message = embedded.get("message", "未返回错误详情")
            raise RuntimeError(f"{error_name}：{error_message}")
        return result

    @staticmethod
    def _embedded_result(result: dict) -> dict | None:
        """解析 MCP content[].text 中被二次 JSON 编码的真实工具返回值。"""
        for item in result.get("content", []):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            try:
                value = json.loads(item["text"])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return None

    def auth_status(self) -> dict:
        return self.call_tool("xhs_auth_status", {})

    def user_notes(self, limit: int = 20) -> list[dict]:
        result = self.call_tool("xhs_get_user_notes", {"limit": limit})
        embedded = self._embedded_result(result) or {}
        data = embedded.get("data", [])
        if isinstance(data, dict):
            data = data.get("notes", data.get("items", []))
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def note_detail(self, feed_id: str, xsec_token: str) -> dict:
        result = self.call_tool("xhs_get_note_detail", {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
        })
        return self._embedded_result(result) or {}

    @classmethod
    def find_value(cls, value, keys: tuple[str, ...]):
        """兼容不同 xhs-mcp 版本，递归读取指定字段。"""
        if isinstance(value, dict):
            for key in keys:
                if key in value and value[key] not in (None, ""):
                    return value[key]
            for nested in value.values():
                found = cls.find_value(nested, keys)
                if found not in (None, ""):
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = cls.find_value(nested, keys)
                if found not in (None, ""):
                    return found
        return None

    @classmethod
    def _note_reference(cls, value) -> str | None:
        """从不同版本的 MCP 返回结构中递归提取真实笔记 URL 或 ID。"""
        if isinstance(value, dict):
            for key in ("url", "noteUrl", "note_url", "shareUrl", "share_url"):
                raw = value.get(key)
                if isinstance(raw, str) and re.match(
                    r"https?://(?:www\.)?xiaohongshu\.com/(?:explore|discovery/item)/[\w-]+",
                    raw,
                    re.IGNORECASE,
                ):
                    return raw
            for key in ("noteId", "note_id", "feedId", "feed_id", "id"):
                raw = value.get(key)
                if isinstance(raw, str) and re.fullmatch(r"[\w-]{8,}", raw):
                    return f"https://www.xiaohongshu.com/explore/{raw}"
            for nested in value.values():
                found = cls._note_reference(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = cls._note_reference(nested)
                if found:
                    return found
        return None

    @staticmethod
    def _note_title(value) -> str:
        if isinstance(value, dict):
            for key in ("title", "displayTitle", "display_title", "name"):
                if isinstance(value.get(key), str):
                    return value[key].strip()
            for nested in value.values():
                title = XhsMcpClient._note_title(nested)
                if title:
                    return title
        return ""

    def publish(self, *, title: str, content: str, media_paths: list[str], tags: list[str]) -> XhsPublishResult:
        # 发布前快照用于在发布响应缺少 note ID 时识别真正新增的笔记。
        before_notes = self.user_notes(limit=20)
        before_refs = {reference for note in before_notes if (reference := self._note_reference(note))}
        result = self.call_tool("xhs_publish_content", {
            "type": "image",
            "title": title,
            "content": content,
            "media_paths": media_paths,
            "tags": ",".join(tags),
        })
        serialized = json.dumps(result, ensure_ascii=False)
        embedded = self._embedded_result(result) or {}
        external_id = self._note_reference(embedded)
        if not external_id:
            normalized_title = re.sub(r"\s+", "", title).casefold()
            for note in self.user_notes(limit=20):
                reference = self._note_reference(note)
                note_title = re.sub(r"\s+", "", self._note_title(note)).casefold()
                if reference and reference not in before_refs and note_title == normalized_title:
                    external_id = reference
                    break
        if not external_id:
            raise RuntimeError("发布响应未返回笔记 ID，且账号笔记列表中未发现标题匹配的新增笔记，不能确认发布成功")
        return XhsPublishResult(external_id=external_id[:160], response_excerpt=serialized[:500])


def validate_xhs_content(title: str, content: str, media_paths: list[str]) -> None:
    display_units = sum(2 if ord(char) > 127 else 1 for char in title)
    if display_units > 40:
        raise ValueError("小红书标题超过40显示单位（中文按2、ASCII按1计算）")
    if len(content) > 1000:
        raise ValueError("小红书正文不能超过1000字符")
    if not 1 <= len(media_paths) <= 18:
        raise ValueError("小红书图文发布需要1至18张图片")
    storage_root = (Path(__file__).resolve().parents[1] / "storage" / "images").resolve()
    for raw_path in media_paths:
        path = Path(raw_path).resolve()
        if not path.is_relative_to(storage_root) or not path.is_file():
            raise ValueError("发布图片必须是项目图片存储目录内的有效文件")
