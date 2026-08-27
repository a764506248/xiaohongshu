import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session, sessionmaker

from app.media import create_package

logger = logging.getLogger(__name__)


class XiaohongshuPackagingState(TypedDict, total=False):
    task_id: str
    package_id: str
    image_count: int


class XiaohongshuPackagingWorkflow:
    """文章主 Graph 完成后的独立小红书平台生产流程。

    图片模型调用由 media.render_pages_parallel 并行执行。该图与文章图分离，
    因此图片失败不会回滚文章审核结果，也不会污染文章图的 checkpoint。
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory
        builder = StateGraph(XiaohongshuPackagingState)
        builder.add_node("generate_xiaohongshu_package", self.generate_package)
        builder.add_edge(START, "generate_xiaohongshu_package")
        builder.add_edge("generate_xiaohongshu_package", END)
        self.graph = builder.compile()

    def start(self, task_id: str) -> dict:
        logger.info("xiaohongshu_packaging.start task_id=%s", task_id)
        return self.graph.invoke({"task_id": task_id})

    def generate_package(self, state: XiaohongshuPackagingState) -> XiaohongshuPackagingState:
        with self.session_factory() as db:
            package = create_package(db, state["task_id"])
            result = {
                **state,
                "package_id": package.id,
                "image_count": len(package.pages),
            }
        logger.info(
            "xiaohongshu_packaging.complete task_id=%s package_id=%s image_count=%d",
            state["task_id"], result["package_id"], result["image_count"],
        )
        return result
