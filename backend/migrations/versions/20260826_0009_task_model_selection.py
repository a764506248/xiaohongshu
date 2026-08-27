"""attach a selectable text model to content tasks"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0009"
down_revision = "20260826_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("content_tasks", sa.Column("model_configuration_id", sa.String(36), nullable=True))
    op.create_index("ix_content_tasks_model_configuration_id", "content_tasks", ["model_configuration_id"])
    op.create_foreign_key(
        "fk_content_tasks_model_configuration_id", "content_tasks", "model_configurations",
        ["model_configuration_id"], ["id"], ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_content_tasks_model_configuration_id", "content_tasks", type_="foreignkey")
    op.drop_index("ix_content_tasks_model_configuration_id", table_name="content_tasks")
    op.drop_column("content_tasks", "model_configuration_id")
