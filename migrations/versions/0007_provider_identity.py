"""Keep a provider object unique within its owner scope."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_repository_provider", "repositories", ["owner_scope", "provider_id"])


def downgrade():
    op.drop_constraint("uq_repository_provider", "repositories", type_="unique")
