import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default="admin")
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    permissions_csv: Mapped[str] = mapped_column("permissions", Text, default="")

    @property
    def permission_codes(self) -> list[str]:
        return [value for value in self.permissions_csv.split(",") if value]


class ContentTask(Base):
    __tablename__ = "content_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(200))
    requirement: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(String(300), default="AI 编程学习者")
    model_configuration_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_configurations.id", ondelete="SET NULL"), nullable=True, index=True
    )
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


class XiaohongshuPackage(Base):
    __tablename__ = "xiaohongshu_packages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_task_id: Mapped[str] = mapped_column(ForeignKey("content_tasks.id", ondelete="CASCADE"), unique=True, index=True)
    article_version_id: Mapped[str] = mapped_column(ForeignKey("article_versions.id"))
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="ready")
    validation_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    pages: Mapped[list["ImagePage"]] = relationship(cascade="all, delete-orphan", order_by="ImagePage.page_number")


class ImagePage(Base):
    __tablename__ = "image_pages"
    __table_args__ = (UniqueConstraint("package_id", "page_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    package_id: Mapped[str] = mapped_column(ForeignKey("xiaohongshu_packages.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(80))
    visual_description: Mapped[str] = mapped_column(Text, default="")
    template: Mapped[str] = mapped_column(String(40), default="editorial")
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    versions: Mapped[list["ImageVersion"]] = relationship(cascade="all, delete-orphan", order_by="ImageVersion.version_number")


class ImageVersion(Base):
    __tablename__ = "image_versions"
    __table_args__ = (UniqueConstraint("page_id", "version_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    page_id: Mapped[str] = mapped_column(ForeignKey("image_pages.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(Text)
    public_url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(30), default="generated")
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=1440)
    file_hash: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChannelAccount(Base):
    __tablename__ = "channel_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(30), index=True)
    mode: Mapped[str] = mapped_column(String(30), default="manual")
    credential_reference: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChannelVariant(Base):
    __tablename__ = "channel_variants"
    __table_args__ = (UniqueConstraint("content_task_id", "channel"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_task_id: Mapped[str] = mapped_column(ForeignKey("content_tasks.id", ondelete="CASCADE"), index=True)
    article_version_id: Mapped[str] = mapped_column(ForeignKey("article_versions.id"))
    channel: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text)
    html_content: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    channel_variant_id: Mapped[str] = mapped_column(ForeignKey("channel_variants.id"), index=True)
    channel_account_id: Mapped[str] = mapped_column(ForeignKey("channel_accounts.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    approval_status: Mapped[str] = mapped_column(String(30), default="pending")
    status: Mapped[str] = mapped_column(String(30), default="pending_approval", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishAttempt(Base):
    __tablename__ = "publish_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    publish_job_id: Mapped[str] = mapped_column(ForeignKey("publish_jobs.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    response_excerpt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PostMetric(Base):
    __tablename__ = "post_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    publish_job_id: Mapped[str] = mapped_column(ForeignKey("publish_jobs.id", ondelete="CASCADE"), index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    favorites: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    follower_gain: Mapped[int] = mapped_column(Integer, default=0)
    performance_score: Mapped[float] = mapped_column(Float, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PreferenceSignal(Base):
    __tablename__ = "preference_signals"
    __table_args__ = (UniqueConstraint("signal_type", "signal_value"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    signal_type: Mapped[str] = mapped_column(String(40))
    signal_value: Mapped[str] = mapped_column(String(160))
    weight: Mapped[float] = mapped_column(Float, default=0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelUsageEvent(Base):
    __tablename__ = "model_usage_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_task_id: Mapped[str | None] = mapped_column(ForeignKey("content_tasks.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(120))
    operation: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ModelConfiguration(Base):
    __tablename__ = "model_configurations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(50), default="aliyun_token_plan")
    model: Mapped[str] = mapped_column(String(120))
    capability: Mapped[str] = mapped_column(String(40))
    protocol: Mapped[str] = mapped_column(String(40), default="dashscope_native")
    base_url: Mapped[str] = mapped_column(String(500))
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @property
    def is_system(self) -> bool:
        return self.owner_user_id is None


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    prompt_key: Mapped[str] = mapped_column(String(160), index=True)
    tags_csv: Mapped[str] = mapped_column("tags", Text, default="")
    scene: Mapped[str] = mapped_column(String(60))
    model_capability: Mapped[str] = mapped_column(String(40), default="text")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="enabled")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    versions: Mapped[list["PromptVersion"]] = relationship(cascade="all, delete-orphan", order_by="PromptVersion.version_number")

    @property
    def tags(self) -> list[str]:
        return [tag for tag in self.tags_csv.split(",") if tag]

    @property
    def is_system(self) -> bool:
        return self.owner_user_id is None

    @property
    def current_version(self):
        return self.versions[-1] if self.versions else None


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_template_id", "version_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    prompt_template_id: Mapped[str] = mapped_column(ForeignKey("prompt_templates.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_prompt_template: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[str] = mapped_column(Text, default="[]")
    change_note: Mapped[str] = mapped_column(String(300), default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
