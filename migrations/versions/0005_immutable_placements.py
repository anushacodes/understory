"""Prevent ready snapshot membership and published evidence from changing."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION preserve_snapshot_membership() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target text;
    BEGIN
      IF TG_OP='DELETE' THEN target=OLD.snapshot_id; ELSE target=NEW.snapshot_id; END IF;
      IF EXISTS (SELECT 1 FROM snapshots WHERE id=target AND state='ready')
      THEN RAISE EXCEPTION 'ready snapshot membership is immutable' USING ERRCODE='23514'; END IF;
      IF TG_OP='UPDATE' THEN
        IF EXISTS (SELECT 1 FROM snapshots WHERE id=OLD.snapshot_id AND state='ready')
        THEN RAISE EXCEPTION 'ready snapshot membership is immutable' USING ERRCODE='23514'; END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$
    """)
    op.execute(
        "CREATE TRIGGER preserve_membership BEFORE INSERT OR UPDATE OR DELETE ON snapshot_files FOR EACH ROW EXECUTE FUNCTION preserve_snapshot_membership()"
    )
    op.execute("""
    CREATE FUNCTION preserve_source_placements() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE src text; cfg text;
    BEGIN
      IF TG_OP='DELETE' THEN src=OLD.source_version_id; ELSE src=NEW.source_version_id; END IF;
      IF TG_TABLE_NAME='passages' THEN
        IF TG_OP='DELETE' THEN cfg=OLD.config_hash; ELSE cfg=NEW.config_hash; END IF;
        IF EXISTS (SELECT 1 FROM snapshots s JOIN snapshot_files f ON f.snapshot_id=s.id WHERE f.source_version_id=src AND s.config_hash=cfg AND s.state='ready')
        THEN RAISE EXCEPTION 'ready passages are immutable' USING ERRCODE='23514'; END IF;
        IF TG_OP='UPDATE' THEN
          IF EXISTS (SELECT 1 FROM snapshots s JOIN snapshot_files f ON f.snapshot_id=s.id WHERE f.source_version_id=OLD.source_version_id AND s.config_hash=OLD.config_hash AND s.state='ready')
          THEN RAISE EXCEPTION 'ready passages are immutable' USING ERRCODE='23514'; END IF;
        END IF;
      ELSE
        IF TG_OP='DELETE' THEN cfg=OLD.parser; ELSE cfg=NEW.parser; END IF;
        IF EXISTS (SELECT 1 FROM snapshots s JOIN snapshot_files f ON f.snapshot_id=s.id WHERE f.source_version_id=src AND s.config->>'parser'=cfg AND s.state='ready')
        THEN RAISE EXCEPTION 'ready symbols are immutable' USING ERRCODE='23514'; END IF;
      END IF;
      IF TG_TABLE_NAME='symbols' AND TG_OP='UPDATE' THEN
        IF EXISTS (SELECT 1 FROM snapshots s JOIN snapshot_files f ON f.snapshot_id=s.id WHERE f.source_version_id=OLD.source_version_id AND s.config->>'parser'=OLD.parser AND s.state='ready')
        THEN RAISE EXCEPTION 'ready symbols are immutable' USING ERRCODE='23514'; END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$
    """)
    for table in ("passages", "symbols"):
        op.execute(
            f"CREATE TRIGGER preserve_placements BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION preserve_source_placements()"
        )
    op.execute("""
    CREATE FUNCTION preserve_run_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target text;
    BEGIN
      IF TG_OP='DELETE' THEN target=OLD.run_id; ELSE target=NEW.run_id; END IF;
      IF EXISTS (SELECT 1 FROM answer_runs WHERE id=target AND output IS NOT NULL)
      THEN RAISE EXCEPTION 'published evidence selections are immutable' USING ERRCODE='23514'; END IF;
      IF TG_OP='UPDATE' THEN
        IF EXISTS (SELECT 1 FROM answer_runs WHERE id=OLD.run_id AND output IS NOT NULL)
        THEN RAISE EXCEPTION 'published evidence selections are immutable' USING ERRCODE='23514'; END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$
    """)
    op.execute(
        "CREATE TRIGGER preserve_evidence BEFORE INSERT OR UPDATE OR DELETE ON run_evidence FOR EACH ROW EXECUTE FUNCTION preserve_run_evidence()"
    )


def downgrade():
    op.execute("DROP TRIGGER preserve_evidence ON run_evidence")
    for table in ("passages", "symbols"):
        op.execute(f"DROP TRIGGER preserve_placements ON {table}")
    op.execute("DROP TRIGGER preserve_membership ON snapshot_files")
    for name in ("preserve_run_evidence", "preserve_source_placements", "preserve_snapshot_membership"):
        op.execute(f"DROP FUNCTION {name}()")
