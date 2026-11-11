"""Protect published snapshots, original source and completed answer inputs."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # json equality needs JSONB conversion because bounded metadata uses JSON columns.
    op.execute("""
    CREATE FUNCTION preserve_published_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='snapshots' THEN
        IF OLD.state='ready' AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)
        THEN RAISE EXCEPTION 'ready snapshots are immutable' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME='source_versions' THEN
        IF to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)
        THEN RAISE EXCEPTION 'source versions are immutable' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME='answer_runs' THEN
        IF OLD.output IS NOT NULL AND (NEW.output::jsonb IS DISTINCT FROM OLD.output::jsonb OR NEW.evidence::jsonb IS DISTINCT FROM OLD.evidence::jsonb OR NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id OR NEW.config::jsonb IS DISTINCT FROM OLD.config::jsonb)
        THEN RAISE EXCEPTION 'published answers are immutable' USING ERRCODE='23514'; END IF;
      END IF;
      RETURN NEW;
    END $$
    """)
    for table in ("snapshots", "source_versions", "answer_runs"):
        op.execute(
            f"CREATE TRIGGER preserve_published BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION preserve_published_evidence()"
        )


def downgrade():
    for table in ("snapshots", "source_versions", "answer_runs"):
        op.execute(f"DROP TRIGGER preserve_published ON {table}")
    op.execute("DROP FUNCTION preserve_published_evidence()")
