import base64
import json
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGIN_ROOT = Path(__file__).resolve().parents[1] / "storage" / "xhs-login"
SCRIPT = PROJECT_ROOT / "xhs-login" / "login.mjs"
NODE_MODULES = PROJECT_ROOT / "xhs-login" / "node_modules"


def start_login_session(timeout_seconds: int = 120) -> dict:
    if not NODE_MODULES.exists():
        raise HTTPException(503, "二维码登录组件尚未安装，请执行 cd xhs-login && npm install")
    session_id = str(uuid.uuid4())
    session_dir = LOGIN_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=False)
    initial = {"status": "starting", "message": "正在生成登录二维码"}
    # 先同步落盘，再启动异步浏览器。否则前端紧接着轮询时会遇到 status.json 尚未创建的竞态。
    (session_dir / "status.json").write_text(json.dumps(initial, ensure_ascii=False), "utf8")
    log_file = (session_dir / "login.log").open("ab")
    try:
        subprocess.Popen(
            ["node", str(SCRIPT), str(session_dir), str(timeout_seconds)],
            cwd=PROJECT_ROOT / "xhs-login",
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        failed = {"status": "failed", "message": f"登录浏览器启动失败：{exc}"}
        (session_dir / "status.json").write_text(json.dumps(failed, ensure_ascii=False), "utf8")
        raise HTTPException(503, failed["message"]) from exc
    finally:
        log_file.close()
    return {"session_id": session_id, **initial}


def login_session_status(session_id: str) -> dict:
    try:
        normalized = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(404, "登录会话不存在") from exc
    session_dir = LOGIN_ROOT / normalized
    if not session_dir.is_dir():
        raise HTTPException(404, "登录会话不存在")
    status_file = session_dir / "status.json"
    if not status_file.is_file():
        # 兼容升级前已经创建、但浏览器脚本尚未来得及写状态的会话。
        return {
            "session_id": normalized,
            "status": "starting",
            "message": "正在生成登录二维码",
        }
    data = json.loads(status_file.read_text("utf8"))
    if (session_dir / "qrcode.png").is_file() and data["status"] == "waiting_scan":
        encoded = base64.b64encode((session_dir / "qrcode.png").read_bytes()).decode("ascii")
        data["qr_image"] = f"data:image/png;base64,{encoded}"
    return {"session_id": normalized, **data}


def login_qrcode_path(session_id: str) -> Path:
    data = login_session_status(session_id)
    path = LOGIN_ROOT / data["session_id"] / "qrcode.png"
    if not path.is_file():
        raise HTTPException(404, "二维码尚未生成或已经失效")
    return path
