"""Keep active execution budgets across retries and worker recovery."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("execution_seconds", sa.Float(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("attempt_started_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("jobs", "attempt_started_at")
    op.drop_column("jobs", "execution_seconds")
