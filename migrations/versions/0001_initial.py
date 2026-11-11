"""Initial scoped repository, source, job and answer schema.

Revision ID: 0001
"""

from alembic import op
from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(op.get_bind())
    op.execute("CREATE INDEX ix_passages_lexical ON passages USING gin (to_tsvector('simple', search_text))")


def downgrade():
    Base.metadata.drop_all(op.get_bind())
