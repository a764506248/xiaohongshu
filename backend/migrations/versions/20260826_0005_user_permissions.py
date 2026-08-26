"""Add user permission codes."""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0005"
down_revision = "20260826_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("permissions", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE users SET permissions='*' WHERE role='admin'")


def downgrade() -> None:
    op.drop_column("users", "permissions")
