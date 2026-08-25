# AI 自媒体运营系统

第一期实现了从内容任务、AI 候选选题、人工选择、文案生成到人工审核的完整闭环。

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

本地 `.env` 默认配置 OpenRouter；自动化测试使用 `mock` 模型，不产生外部调用或模型费用。需要离线运行时可将 `LLM_PROVIDER` 改为 `mock`。
