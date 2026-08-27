# AI 自媒体运营系统

当前已实现从内容任务、AI 候选选题、人工选择、文案生成、人工审核到小红书图文内容包的完整闭环。

## 已实现功能

- AI 候选选题与人工选择
- Markdown 技术文章生成、版本管理与人工审核
- 文章压缩为 3～5 张小红书竖版图片
- 三套视觉模板、文字重排版和单张重新生成
- 人工上传图片替换与图片顺序调整
- 小红书标题、正文和话题标签编辑
- PNG 图片、`content.json` 和发布文案 ZIP 导出

## 项目结构

```text
backend/   FastAPI、LangGraph、SQLAlchemy、PostgreSQL
frontend/  React、TypeScript、Vite
docs/      分期执行计划
```

## 本地启动

### 1. PostgreSQL

```bash
docker compose up -d postgres
```

### 2. 后端

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

后端地址为 `http://localhost:8000`，接口文档位于 `http://localhost:8000/docs`。

小红书账号需要扫码登录时，先安装二维码登录桥接组件（仅首次需要）：

```bash
cd xhs-login
npm install
```

后端通过本机 stdio 子进程调用 XHS MCP，无需启动 HTTP 服务，也不会开放 3000 端口。“多平台运营”中的“检测登录”会先查询 XHS MCP；未登录时自动弹出二维码，并把扫码后的 Cookie 保存到 `~/.xhs-mcp/cookies.json` 供检测和发布复用。

本地开发默认使用 Docker PostgreSQL，同时保存业务数据和 LangGraph checkpoint。自动化测试使用隔离的 SQLite 与内存 checkpoint，不会修改本地开发数据。

### 3. 前端

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

前端地址为 `http://localhost:5173`。

## 验证

```bash
cd backend && uv run pytest -q
cd frontend && npm run build
```

本地 `.env` 默认配置 SenseNova Messages API 和 `deepseek-v4-flash`；自动化测试使用 `mock` 模型，不产生外部调用或模型费用。需要离线运行时可将 `LLM_PROVIDER` 改为 `mock`，也可切换回保留的 OpenRouter 适配器。

## LangSmith 链路追踪

后端已支持 LangSmith 观测 LangGraph 主图、选题子图、节点耗时、异常和任务元数据。在 `backend/.env` 中配置后重启后端：

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_你的密钥
LANGSMITH_PROJECT=xiaohongshu-content-operations
```

每条 trace 都带有 `task_id`、LangGraph `thread_id` 和任务选择的模型配置 ID。若不希望任务要求及生成内容离开服务器，可同时启用：

```env
LANGSMITH_HIDE_INPUTS=true
LANGSMITH_HIDE_OUTPUTS=true
```
