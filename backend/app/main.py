import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver

from app.ai.provider import get_llm_provider
from app.api import router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.workflows.content_creation.graph import ContentWorkflow

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    settings = get_settings()
    checkpoint_context = None
    if settings.checkpoint_database_url:
        from langgraph.checkpoint.postgres import PostgresSaver
        checkpoint_context = PostgresSaver.from_conn_string(settings.checkpoint_database_url)
        checkpointer = checkpoint_context.__enter__()
        checkpointer.setup()
    else:
        checkpointer = InMemorySaver()
    app.state.workflow = ContentWorkflow(SessionLocal, get_llm_provider(), checkpointer)
    yield
    if checkpoint_context:
        checkpoint_context.__exit__(None, None, None)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
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

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()

