"""add model configurations"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0006"
down_revision = "20260826_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(40), nullable=False),
        sa.Column("protocol", sa.String(40), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "model"),
    )


def downgrade():
    op.drop_table("model_configurations")
