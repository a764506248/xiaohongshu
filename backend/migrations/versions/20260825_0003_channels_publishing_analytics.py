"""Add channel variants, publishing and analytics."""
from alembic import op
import sqlalchemy as sa

revision = "20260825_0003"
down_revision = "20260825_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("channel_accounts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False), sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("credential_reference", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_channel_accounts_channel", "channel_accounts", ["channel"])
    op.create_table("channel_variants",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("content_task_id", sa.String(36), sa.ForeignKey("content_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_version_id", sa.String(36), sa.ForeignKey("article_versions.id"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=False), sa.Column("cover_url", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("content_task_id", "channel"))
    op.create_index("ix_channel_variants_content_task_id", "channel_variants", ["content_task_id"])
    op.create_index("ix_channel_variants_channel", "channel_variants", ["channel"])
    op.create_table("publish_jobs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("channel_variant_id", sa.String(36), sa.ForeignKey("channel_variants.id"), nullable=False),
        sa.Column("channel_account_id", sa.String(36), sa.ForeignKey("channel_accounts.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), unique=True, nullable=False),
        sa.Column("approval_status", sa.String(30), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("scheduled_at", sa.DateTime()), sa.Column("published_at", sa.DateTime()),
        sa.Column("external_post_id", sa.String(160)), sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False), sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_publish_jobs_channel_variant_id", "publish_jobs", ["channel_variant_id"])
    op.create_index("ix_publish_jobs_channel_account_id", "publish_jobs", ["channel_account_id"])
    op.create_index("ix_publish_jobs_status", "publish_jobs", ["status"])
    op.create_index("ix_publish_jobs_scheduled_at", "publish_jobs", ["scheduled_at"])
    op.create_table("publish_attempts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("publish_job_id", sa.String(36), sa.ForeignKey("publish_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("response_excerpt", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_publish_attempts_publish_job_id", "publish_attempts", ["publish_job_id"])
    op.create_table("post_metrics",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("publish_job_id", sa.String(36), sa.ForeignKey("publish_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False), sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("favorites", sa.Integer(), nullable=False), sa.Column("comments", sa.Integer(), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False), sa.Column("follower_gain", sa.Integer(), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=False), sa.Column("collected_at", sa.DateTime(), nullable=False))
    op.create_index("ix_post_metrics_publish_job_id", "post_metrics", ["publish_job_id"])
    op.create_index("ix_post_metrics_collected_at", "post_metrics", ["collected_at"])
    op.create_table("preference_signals",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("signal_type", sa.String(40), nullable=False),
        sa.Column("signal_value", sa.String(160), nullable=False), sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("signal_type", "signal_value"))
    op.create_table("model_usage_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("content_task_id", sa.String(36), sa.ForeignKey("content_tasks.id")),
        sa.Column("provider", sa.String(50), nullable=False), sa.Column("model", sa.String(120), nullable=False),
        sa.Column("operation", sa.String(60), nullable=False), sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False), sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_model_usage_events_content_task_id", "model_usage_events", ["content_task_id"])
    op.create_index("ix_model_usage_events_created_at", "model_usage_events", ["created_at"])


def downgrade() -> None:
    for table in ["model_usage_events", "preference_signals", "post_metrics", "publish_attempts", "publish_jobs", "channel_variants", "channel_accounts"]:
        op.drop_table(table)
