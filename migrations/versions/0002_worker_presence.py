"""Persist idle worker availability separately from job leases."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "worker_presence",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("worker_presence")
