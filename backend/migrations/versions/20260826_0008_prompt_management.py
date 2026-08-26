"""add prompt management"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0008"
down_revision = "20260826_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("prompt_templates",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_user_id",sa.String(36),nullable=True),
        sa.Column("name",sa.String(120),nullable=False),sa.Column("prompt_key",sa.String(160),nullable=False),
        sa.Column("tags",sa.Text(),nullable=False),sa.Column("scene",sa.String(60),nullable=False),
        sa.Column("model_capability",sa.String(40),nullable=False),sa.Column("description",sa.Text(),nullable=False),
        sa.Column("status",sa.String(30),nullable=False),sa.Column("is_default",sa.Boolean(),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"],["users.id"],ondelete="CASCADE"))
    op.create_index("ix_prompt_templates_owner_user_id","prompt_templates",["owner_user_id"])
    op.create_index("ix_prompt_templates_prompt_key","prompt_templates",["prompt_key"])
    op.create_table("prompt_versions",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("prompt_template_id",sa.String(36),nullable=False),
        sa.Column("version_number",sa.Integer(),nullable=False),sa.Column("system_prompt",sa.Text(),nullable=False),
        sa.Column("user_prompt_template",sa.Text(),nullable=False),sa.Column("variables_json",sa.Text(),nullable=False),
        sa.Column("change_note",sa.String(300),nullable=False),sa.Column("created_by",sa.String(36),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["prompt_template_id"],["prompt_templates.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"],["users.id"],ondelete="SET NULL"),
        sa.UniqueConstraint("prompt_template_id","version_number"))
    op.create_index("ix_prompt_versions_prompt_template_id","prompt_versions",["prompt_template_id"])


def downgrade():
    op.drop_table("prompt_versions"); op.drop_table("prompt_templates")
