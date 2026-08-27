import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import InMemorySaver

from app.ai.provider import get_llm_provider
from app.api import router
from app.auth import ensure_default_admin, get_current_user, router as auth_router
from app.user_api import router as user_router
from app.model_api import router as model_router
from app.prompt_api import router as prompt_router
from app.prompt_service import seed_system_prompts
from app.aliyun_models import seed_model_configurations
from app.operations_api import router as operations_router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.workflows.content_creation.graph import ContentWorkflow
from app.workflows.xiaohongshu_packaging import XiaohongshuPackagingWorkflow
from app.media import STORAGE_ROOT

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    settings = get_settings()
    # Pydantic 会读取 backend/.env，但 LangSmith SDK 直接读取进程环境变量，
    # 因此在创建/调用 LangGraph 前同步一次配置。
    os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_HIDE_INPUTS"] = str(settings.langsmith_hide_inputs).lower()
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = str(settings.langsmith_hide_outputs).lower()
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id
    with SessionLocal() as db:
        ensure_default_admin(db)
        seed_model_configurations(db)
        seed_system_prompts(db)
    checkpoint_context = None
    if settings.checkpoint_database_url:
        from langgraph.checkpoint.postgres import PostgresSaver
        checkpoint_context = PostgresSaver.from_conn_string(settings.checkpoint_database_url)
        checkpointer = checkpoint_context.__enter__()
        checkpointer.setup()
    else:
        checkpointer = InMemorySaver()
    app.state.workflow = ContentWorkflow(SessionLocal, get_llm_provider(), checkpointer)
    # 小红书平台生产使用独立 Graph，在文章主图完成后运行。
    app.state.xiaohongshu_packaging_workflow = XiaohongshuPackagingWorkflow(SessionLocal)
    yield
    if checkpoint_context:
        checkpoint_context.__exit__(None, None, None)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "基于 FastAPI、LangGraph 和 PostgreSQL 的 AI 自媒体内容生产 API。\n\n"
            "推荐调用顺序：创建任务 → 生成候选选题 → 选择选题 → 审核文章 → 生成小红书内容包。\n\n"
            "当前为内部运营系统，尚未启用登录鉴权。耗时的模型接口可能需要等待数十秒。"
        ),
        openapi_tags=[
            {"name": "系统", "description": "服务健康状态和基础信息。"},
            {"name": "用户认证", "description": "后台管理员登录和当前用户信息。"},
            {"name": "用户权限", "description": "创建用户、启停账号、重置密码和分配 RBAC 权限。"},
            {"name": "模型管理", "description": "查看、启停、设置默认模型并执行连通性测试。API Key 不会通过接口返回。"},
            {"name": "Prompt 管理", "description": "管理系统和个人 Prompt、标签、模板变量及不可变版本历史。"},
            {"name": "内容任务", "description": "内容生产流程的根对象；任务状态决定前端当前展示的操作。"},
            {"name": "候选选题", "description": "调用 LLM 生成候选选题，并通过人工选择恢复 LangGraph。"},
            {"name": "文章与版本", "description": "查询 AI 文案、历史版本以及保存人工编辑版本。历史版本不会被覆盖。"},
            {"name": "人工审核", "description": "通过、退回、重新生成或人工修改后通过文章。request_id 用于幂等。"},
            {"name": "小红书内容包", "description": "将审核完成的文章转换为发布文案、3～5 张图片和 ZIP。"},
            {"name": "图片页面", "description": "编辑图片文字、切换模板、重新生成或上传人工替换图片。"},
            {"name": "渠道账号", "description": "管理小红书和微信公众号账号；凭证只保存外部引用。"},
            {"name": "多平台内容", "description": "把审核终稿转换为小红书和微信公众号独立版本。"},
            {"name": "发布任务", "description": "发布审批、排期、幂等执行、人工确认和失败重试。"},
            {"name": "运营数据", "description": "发布指标回流、偏好信号、标题查重和模型成本。"},
        ],
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

    @app.get("/health", tags=["系统"], summary="检查服务健康状态", description="用于本地启动检查、容器健康检查和部署探针。")
    def health():
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(model_router)
    app.include_router(prompt_router)
    app.include_router(router, dependencies=[Depends(get_current_user)])
    app.include_router(operations_router, dependencies=[Depends(get_current_user)])
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=STORAGE_ROOT), name="media")
    return app


app = create_app()
