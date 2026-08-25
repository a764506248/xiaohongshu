from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.provider import LLMProvider, TopicOutput
from app.models import Article, ArticleVersion, ContentTask, ReviewRecord, TaskStatus, TopicCandidate
from app.workflows.content_creation.state import ContentState


class ContentWorkflow:
    def __init__(self, session_factory: sessionmaker[Session], llm: LLMProvider, checkpointer):
        self.session_factory = session_factory
        self.llm = llm
        builder = StateGraph(ContentState)
        builder.add_node("generate_topics", self.generate_topics)
        builder.add_node("select_topic", self.select_topic)
        builder.add_node("generate_article", self.generate_article)
        builder.add_node("review_article", self.review_article)
        builder.add_node("finish", self.finish)
        builder.add_edge(START, "generate_topics")
        builder.add_edge("generate_topics", "select_topic")
        builder.add_edge("select_topic", "generate_article")
        builder.add_edge("generate_article", "review_article")
        builder.add_conditional_edges(
            "review_article",
            lambda state: state.get("review", {}).get("decision", "approve"),
            {"approve": "finish", "edit_and_approve": "finish", "reject": "generate_article", "regenerate": "generate_article"},
        )
        builder.add_edge("finish", END)
        self.graph = builder.compile(checkpointer=checkpointer)

    @staticmethod
    def config(task: ContentTask | str) -> dict:
        task_id = task if isinstance(task, str) else task.id
        return {"configurable": {"thread_id": f"content-task:{task_id}"}}

    def start(self, task_id: str, instruction: str = ""):
        return self.graph.invoke({"task_id": task_id, "instruction": instruction}, self.config(task_id))

    def resume(self, task_id: str, value: dict):
        return self.graph.invoke(Command(resume=value), self.config(task_id))

    def generate_topics(self, state: ContentState) -> ContentState:
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            if not task:
                raise ValueError("内容任务不存在")
            task.status = TaskStatus.generating_topics
            task.current_stage = "generating_topics"
            task.workflow_thread_id = f"content-task:{task.id}"
            db.query(TopicCandidate).filter(TopicCandidate.content_task_id == task.id).delete()
            outputs = self.llm.generate_topics(task.title, task.requirement, task.target_audience, state.get("instruction", ""))
            for output in outputs:
                db.add(TopicCandidate(content_task_id=task.id, **output.__dict__))
            task.status = TaskStatus.waiting_topic_selection
            task.current_stage = "waiting_topic_selection"
            db.commit()
        return state

    def select_topic(self, state: ContentState) -> ContentState:
        selection = interrupt({"kind": "topic_selection", "task_id": state["task_id"]})
        topic_id = selection["topic_id"]
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            topic = db.get(TopicCandidate, topic_id)
            if not task or not topic or topic.content_task_id != task.id:
                raise ValueError("候选选题无效")
            db.query(TopicCandidate).filter(TopicCandidate.content_task_id == task.id).update({"status": "candidate"})
            topic.status = "selected"
            task.selected_topic_id = topic.id
            task.status = TaskStatus.generating_article
            task.current_stage = "generating_article"
            db.commit()
        return {**state, "topic_id": topic_id}

    def generate_article(self, state: ContentState) -> ContentState:
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            topic = db.get(TopicCandidate, task.selected_topic_id) if task else None
            if not task or not topic:
                raise ValueError("未找到已选选题")
            review = state.get("review", {})
            instruction = review.get("comment", "") or state.get("instruction", "")
            output = self.llm.generate_article(
                TopicOutput(topic.title, topic.summary, topic.target_reader, topic.reason, topic.score), instruction
            )
            article = db.scalar(select(Article).where(Article.content_task_id == task.id))
            if not article:
                article = Article(content_task_id=task.id, selected_topic_id=topic.id)
                db.add(article)
                db.flush()
            next_version = (db.scalar(select(func.max(ArticleVersion.version_number)).where(ArticleVersion.article_id == article.id)) or 0) + 1
            source_type = "ai_revised" if next_version > 1 else "ai_generated"
            version = ArticleVersion(
                article_id=article.id,
                version_number=next_version,
                title=output.title,
                outline=output.outline,
                content=output.content,
                generation_instruction=instruction,
                source_type=source_type,
            )
            db.add(version)
            db.flush()
            article.current_version_id = version.id
            article.status = "waiting_review"
            task.status = TaskStatus.waiting_article_review
            task.current_stage = "waiting_article_review"
            db.commit()
            article_id = article.id
        return {**state, "article_id": article_id, "review": {}}

    def review_article(self, state: ContentState) -> ContentState:
        review = interrupt({"kind": "article_review", "task_id": state["task_id"], "article_id": state["article_id"]})
        return {**state, "review": review}

    def finish(self, state: ContentState) -> ContentState:
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            article = db.scalar(select(Article).where(Article.content_task_id == state["task_id"]))
            if task:
                task.status = TaskStatus.completed
                task.current_stage = "completed"
            if article:
                article.status = "approved"
            db.commit()
        return state

