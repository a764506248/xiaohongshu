"""Initial content workflow schema."""

from alembic import op
import sqlalchemy as sa

revision = "20260825_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("content_tasks",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=False), sa.Column("target_audience", sa.String(300), nullable=False),
        sa.Column("status", sa.Enum("draft", "generating_topics", "waiting_topic_selection", "generating_article", "waiting_article_review", "completed", "failed", name="taskstatus"), nullable=False),
        sa.Column("current_stage", sa.String(80), nullable=False), sa.Column("selected_topic_id", sa.String(36)),
        sa.Column("workflow_thread_id", sa.String(100), unique=True), sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("topic_candidates",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("content_task_id", sa.String(36), sa.ForeignKey("content_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(250), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("target_reader", sa.String(300), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_topic_candidates_content_task_id", "topic_candidates", ["content_task_id"])
    op.create_table("articles",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("content_task_id", sa.String(36), sa.ForeignKey("content_tasks.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("selected_topic_id", sa.String(36), sa.ForeignKey("topic_candidates.id"), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_version_id", sa.String(36)), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("article_versions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("article_id", sa.String(36), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("title", sa.String(250), nullable=False),
        sa.Column("outline", sa.Text(), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("generation_instruction", sa.Text(), nullable=False), sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("article_id", "version_number"))
    op.create_index("ix_article_versions_article_id", "article_versions", ["article_id"])
    op.create_table("review_records",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("request_id", sa.String(100), unique=True, nullable=False),
        sa.Column("content_task_id", sa.String(36), sa.ForeignKey("content_tasks.id"), nullable=False),
        sa.Column("article_version_id", sa.String(36), sa.ForeignKey("article_versions.id"), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False), sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.String(80), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_review_records_content_task_id", "review_records", ["content_task_id"])


def downgrade() -> None:
    op.drop_table("review_records")
    op.drop_table("article_versions")
    op.drop_table("articles")
    op.drop_table("topic_candidates")
    op.drop_table("content_tasks")
    sa.Enum(name="taskstatus").drop(op.get_bind(), checkfirst=True)
