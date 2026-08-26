"""support user owned model configurations"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0007"
down_revision = "20260826_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("model_configurations_provider_model_key", "model_configurations", type_="unique")
    op.add_column("model_configurations", sa.Column("owner_user_id", sa.String(36), nullable=True))
    op.add_column("model_configurations", sa.Column("api_key", sa.Text(), nullable=True))
    op.create_index("ix_model_configurations_owner_user_id", "model_configurations", ["owner_user_id"])
    op.create_foreign_key("fk_model_configurations_owner_user_id", "model_configurations", "users", ["owner_user_id"], ["id"], ondelete="CASCADE")


def downgrade():
    op.drop_constraint("fk_model_configurations_owner_user_id", "model_configurations", type_="foreignkey")
    op.drop_index("ix_model_configurations_owner_user_id", table_name="model_configurations")
    op.drop_column("model_configurations", "api_key")
    op.drop_column("model_configurations", "owner_user_id")
    op.create_unique_constraint("model_configurations_provider_model_key", "model_configurations", ["provider", "model"])
