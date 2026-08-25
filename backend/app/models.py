import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class TaskStatus(str, enum.Enum):
    draft = "draft"
    generating_topics = "generating_topics"
    waiting_topic_selection = "waiting_topic_selection"
    generating_article = "generating_article"
    waiting_article_review = "waiting_article_review"
    completed = "completed"
    failed = "failed"


class ContentTask(Base):
    __tablename__ = "content_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(200))
    requirement: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(String(300), default="AI 编程学习者")
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.draft)
    current_stage: Mapped[str] = mapped_column(String(80), default="draft")
    selected_topic_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    topics: Mapped[list["TopicCandidate"]] = relationship(cascade="all, delete-orphan")
    article: Mapped["Article | None"] = relationship(back_populates="task", uselist=False)


class TopicCandidate(Base):
    __tablename__ = "topic_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_task_id: Mapped[str] = mapped_column(ForeignKey("content_tasks.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(250))
    summary: Mapped[str] = mapped_column(Text)
    target_reader: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_task_id: Mapped[str] = mapped_column(ForeignKey("content_tasks.id", ondelete="CASCADE"), unique=True)
    selected_topic_id: Mapped[str] = mapped_column(ForeignKey("topic_candidates.id"))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    task: Mapped[ContentTask] = relationship(back_populates="article")
    versions: Mapped[list["ArticleVersion"]] = relationship(cascade="all, delete-orphan", order_by="ArticleVersion.version_number")


class ArticleVersion(Base):
    __tablename__ = "article_versions"
    __table_args__ = (UniqueConstraint("article_id", "version_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(250))
    outline: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)
    generation_instruction: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewRecord(Base):
    __tablename__ = "review_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    request_id: Mapped[str] = mapped_column(String(100), unique=True)
    content_task_id: Mapped[str] = mapped_column(ForeignKey("content_tasks.id"), index=True)
    article_version_id: Mapped[str] = mapped_column(ForeignKey("article_versions.id"))
    decision: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[str] = mapped_column(String(80), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

