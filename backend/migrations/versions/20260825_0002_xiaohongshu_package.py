"""Add Xiaohongshu content packages and image versions."""

from alembic import op
import sqlalchemy as sa

revision = "20260825_0002"
down_revision = "20260825_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("xiaohongshu_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_task_id", sa.String(36), sa.ForeignKey("content_tasks.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("article_version_id", sa.String(36), sa.ForeignKey("article_versions.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_xiaohongshu_packages_content_task_id", "xiaohongshu_packages", ["content_task_id"])
    op.create_table("image_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("xiaohongshu_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False), sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("purpose", sa.String(80), nullable=False),
        sa.Column("visual_description", sa.Text(), nullable=False), sa.Column("template", sa.String(40), nullable=False),
        sa.Column("current_version_id", sa.String(36)), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("package_id", "page_number"))
    op.create_index("ix_image_pages_package_id", "image_pages", ["package_id"])
    op.create_table("image_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("image_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("public_url", sa.Text(), nullable=False), sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False), sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False), sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("page_id", "version_number"))
    op.create_index("ix_image_versions_page_id", "image_versions", ["page_id"])


def downgrade() -> None:
    op.drop_table("image_versions")
    op.drop_table("image_pages")
    op.drop_table("xiaohongshu_packages")

