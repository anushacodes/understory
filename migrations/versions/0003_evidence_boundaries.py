"""Enforce provenance at the database boundary, not only in service code."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "run_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(32), sa.ForeignKey("answer_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "repository_id",
            sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.String(32), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("source_version_id", sa.String(32), sa.ForeignKey("source_versions.id"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.UniqueConstraint("run_id", "evidence_id"),
        sa.CheckConstraint("start_line >= 1 AND end_line >= start_line"),
    )
    op.create_index("ix_run_evidence_run_id", "run_evidence", ["run_id"])
    op.execute("""
    CREATE FUNCTION enforce_repository_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME = 'repositories' THEN
        IF NEW.active_snapshot_id IS NOT NULL AND NOT EXISTS
          (SELECT 1 FROM snapshots s WHERE s.id=NEW.active_snapshot_id AND s.repository_id=NEW.id AND s.state='ready')
        THEN RAISE EXCEPTION 'active snapshot scope/state mismatch' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME = 'jobs' THEN
        IF NOT EXISTS (SELECT 1 FROM repositories r WHERE r.id=NEW.repository_id AND r.owner_scope=NEW.owner_scope)
          OR (NEW.snapshot_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM snapshots s WHERE s.id=NEW.snapshot_id AND s.repository_id=NEW.repository_id))
        THEN RAISE EXCEPTION 'job repository scope mismatch' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME = 'snapshot_files' THEN
        IF (NEW.state='included' AND NEW.source_version_id IS NULL) OR
          (NEW.source_version_id IS NOT NULL AND NOT EXISTS
          (SELECT 1 FROM snapshots s JOIN source_versions v ON v.repository_id=s.repository_id WHERE s.id=NEW.snapshot_id AND v.id=NEW.source_version_id AND v.path=NEW.path))
        THEN RAISE EXCEPTION 'manifest source scope mismatch' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME = 'answer_runs' THEN
        IF NOT EXISTS (SELECT 1 FROM jobs j JOIN snapshots s ON s.id=NEW.snapshot_id WHERE j.id=NEW.job_id AND j.repository_id=NEW.repository_id AND j.snapshot_id=NEW.snapshot_id AND s.repository_id=NEW.repository_id AND s.state='ready')
        THEN RAISE EXCEPTION 'answer baseline scope mismatch' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME = 'run_evidence' THEN
        IF NOT EXISTS (SELECT 1 FROM answer_runs r JOIN snapshot_files f ON f.snapshot_id=r.snapshot_id JOIN source_versions v ON v.id=f.source_version_id
          WHERE r.id=NEW.run_id AND r.repository_id=NEW.repository_id AND r.snapshot_id=NEW.snapshot_id AND v.id=NEW.source_version_id AND v.repository_id=r.repository_id AND f.path=NEW.path AND f.state='included' AND NEW.end_line<=v.line_count)
        THEN RAISE EXCEPTION 'evidence snapshot/source mismatch' USING ERRCODE='23514'; END IF;
      END IF;
      RETURN NEW;
    END $$
    """)
    for table in ("repositories", "jobs", "snapshot_files", "answer_runs", "run_evidence"):
        op.execute(
            f"CREATE TRIGGER enforce_scope BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION enforce_repository_scope()"
        )
    op.execute(
        "ALTER TABLE symbols ADD CONSTRAINT valid_symbol_range CHECK (start_line >= 1 AND end_line >= start_line)"
    )
    op.execute(
        "ALTER TABLE passages ADD CONSTRAINT valid_passage_range CHECK (start_line >= 1 AND end_line >= start_line)"
    )


def downgrade():
    for table in ("repositories", "jobs", "snapshot_files", "answer_runs", "run_evidence"):
        op.execute(f"DROP TRIGGER enforce_scope ON {table}")
    op.execute("DROP FUNCTION enforce_repository_scope()")
    op.execute("ALTER TABLE symbols DROP CONSTRAINT valid_symbol_range")
    op.execute("ALTER TABLE passages DROP CONSTRAINT valid_passage_range")
    op.drop_table("run_evidence")
