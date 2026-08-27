import logging
import re
from difflib import SequenceMatcher
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.provider import LLMProvider, TopicOutput
from app.models import ContentTask, ModelUsageEvent, TaskStatus, TopicCandidate

logger = logging.getLogger(__name__)


class TopicGenerationState(TypedDict, total=False):
    """选题子图状态；候选内容仅在子图执行期间流转。"""

    task_id: str
    instruction: str
    llm_topic_count: int
    rag_topic_count: int
    llm_topics: list[dict]
    rag_topics: list[dict]
    merged_topics: list[dict]


class TopicGenerationSubgraph:
    """组合多个选题来源，并将最终候选保存到业务数据库。"""

    def __init__(self, session_factory: sessionmaker[Session], llm_resolver: Callable[[Session, ContentTask], LLMProvider]):
        self.session_factory = session_factory
        self.llm_resolver = llm_resolver

        builder = StateGraph(TopicGenerationState)
        builder.add_node("initialize", self.initialize)
        builder.add_node("generate_llm_topics", self.generate_llm_topics)
        builder.add_node("retrieve_rag_topics", self.retrieve_rag_topics)
        builder.add_node("merge_and_rank_topics", self.merge_and_rank_topics)
        builder.add_node("persist_topics", self.persist_topics)

        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "generate_llm_topics")
        builder.add_edge("generate_llm_topics", "retrieve_rag_topics")
        builder.add_edge("retrieve_rag_topics", "merge_and_rank_topics")
        builder.add_edge("merge_and_rank_topics", "persist_topics")
        builder.add_edge("persist_topics", END)
        self.graph = builder.compile()

    def initialize(self, state: TopicGenerationState) -> TopicGenerationState:
        """清理旧候选，并把任务切换为选题生成中。"""
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            if not task:
                raise ValueError("内容任务不存在")
            task.status = TaskStatus.generating_topics
            task.current_stage = "generating_topics"
            task.error_message = None
            db.query(TopicCandidate).filter(TopicCandidate.content_task_id == task.id).delete()
            db.commit()
        return {
            **state,
            "llm_topic_count": max(1, state.get("llm_topic_count", 4)),
            "rag_topic_count": max(0, state.get("rag_topic_count", 3)),
            "llm_topics": [],
            "rag_topics": [],
        }

    def generate_llm_topics(self, state: TopicGenerationState) -> TopicGenerationState:
        """调用大模型生成 N 条新选题。"""
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            if not task:
                raise ValueError("内容任务不存在")
            llm = self.llm_resolver(db, task)
            outputs = llm.generate_topics(
                task.title,
                task.requirement,
                task.target_audience,
                state.get("instruction", ""),
            )[: state["llm_topic_count"]]
            self._save_usage(db, task.id, "generate_topics", llm)
            db.commit()
        logger.info("topic_subgraph.llm_complete task_id=%s count=%d", state["task_id"], len(outputs))
        return {**state, "llm_topics": [output.__dict__ for output in outputs]}

    def retrieve_rag_topics(self, state: TopicGenerationState) -> TopicGenerationState:
        """从历史候选选题中召回与当前任务最相关的 N 条。"""
        limit = state["rag_topic_count"]
        if limit == 0:
            return {**state, "rag_topics": []}
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            if not task:
                raise ValueError("内容任务不存在")
            history = list(db.scalars(
                select(TopicCandidate)
                .where(TopicCandidate.content_task_id != task.id)
                .order_by(TopicCandidate.created_at.desc())
                .limit(200)
            ))
            ranked = sorted(
                history,
                key=lambda topic: SequenceMatcher(None, task.title.lower(), topic.title.lower()).ratio(),
                reverse=True,
            )[:limit]
            rag_topics = [
                TopicOutput(
                    title=topic.title,
                    summary=topic.summary,
                    target_reader=topic.target_reader,
                    reason=f"RAG 历史召回：{topic.reason}",
                    score=min(100.0, topic.score),
                ).__dict__
                for topic in ranked
            ]
        logger.info("topic_subgraph.rag_complete task_id=%s count=%d", state["task_id"], len(rag_topics))
        return {**state, "rag_topics": rag_topics}

    def merge_and_rank_topics(self, state: TopicGenerationState) -> TopicGenerationState:
        """合并各来源候选，按规范化标题去重，再按评分降序排列。"""
        unique: dict[str, dict] = {}
        for topic in [*state.get("llm_topics", []), *state.get("rag_topics", [])]:
            key = re.sub(r"[^\w\u4e00-\u9fff]", "", topic["title"].lower())
            previous = unique.get(key)
            if previous is None or topic["score"] > previous["score"]:
                unique[key] = topic
        merged = sorted(unique.values(), key=lambda topic: topic["score"], reverse=True)
        logger.info("topic_subgraph.merge_complete task_id=%s count=%d", state["task_id"], len(merged))
        return {**state, "merged_topics": merged}

    def persist_topics(self, state: TopicGenerationState) -> TopicGenerationState:
        """只在所有来源与排序都成功后，一次性写入最终候选。"""
        topics = state.get("merged_topics", [])
        if not topics:
            raise ValueError("没有生成可用的候选选题")
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            if not task:
                raise ValueError("内容任务不存在")
            for topic in topics:
                db.add(TopicCandidate(content_task_id=task.id, **topic))
            task.status = TaskStatus.waiting_topic_selection
            task.current_stage = "waiting_topic_selection"
            db.commit()
        logger.info("topic_subgraph.persist_complete task_id=%s count=%d", state["task_id"], len(topics))
        return state

    def _save_usage(self, db: Session, task_id: str, operation: str, llm: LLMProvider) -> None:
        usage = llm.consume_usage()
        if not usage:
            logger.warning("llm_usage.missing task_id=%s operation=%s", task_id, operation)
            return
        db.add(ModelUsageEvent(
            content_task_id=task_id,
            provider=usage.provider,
            model=usage.model,
            operation=operation,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost=0,
            latency_ms=usage.latency_ms,
            status=usage.status,
        ))
