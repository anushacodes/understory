import pytest
from app.db import SessionLocal
from app.jobs import enqueue
from app.models import Job, Repository, RunEvidence, Snapshot, SnapshotFile, SourceVersion
from sqlalchemy.exc import IntegrityError


def seed_boundaries():
    with SessionLocal.begin() as session:
        a, b = Repository(name="example/a"), Repository(name="example/b")
        session.add_all([a, b])
        session.flush()
        snap_a = Snapshot(
            repository_id=a.id,
            commit_sha="a" * 40,
            config_hash="a",
            config={"parser": "test"},
            state="staging",
        )
        snap_b = Snapshot(
            repository_id=b.id, commit_sha="b" * 40, config_hash="b", config={"parser": "test"}, state="ready"
        )
        source_b = SourceVersion(
            repository_id=b.id,
            path="source.py",
            content_hash="b",
            content="x = 1\n",
            kind="code",
            line_count=1,
            byte_count=6,
        )
        session.add_all([snap_a, snap_b, source_b])
        session.flush()
        return a.id, b.id, snap_a.id, snap_b.id, source_b.id


@pytest.mark.parametrize("target", ["foreign", "staging"])
def test_active_pointer_rejects_foreign_and_staging_snapshots(database, target):
    a, _, snap_a, snap_b, _ = seed_boundaries()
    with pytest.raises(IntegrityError), SessionLocal.begin() as session:
        session.get(Repository, a).active_snapshot_id = snap_b if target == "foreign" else snap_a
        session.flush()


def test_manifest_cannot_point_to_another_repository_source(database):
    _, _, snap_a, _, source_b = seed_boundaries()
    with pytest.raises(IntegrityError), SessionLocal.begin() as session:
        session.add(
            SnapshotFile(
                snapshot_id=snap_a,
                path="source.py",
                source_version_id=source_b,
                byte_count=6,
                state="included",
            )
        )
        session.flush()


def test_job_scope_is_enforced_even_on_raw_database_writes(database):
    a, _, _, snap_b, _ = seed_boundaries()
    with pytest.raises(IntegrityError), SessionLocal.begin() as session:
        session.add(
            Job(
                repository_id=a,
                owner_scope="owner",
                snapshot_id=snap_b,
                kind="question",
                request={},
                request_hash="x",
                idempotency_key="foreign",
            )
        )
        session.flush()


def test_normalized_evidence_rejects_cross_snapshot_source(database):
    a, _, snap_a, _, source_b = seed_boundaries()
    with SessionLocal.begin() as session:
        snapshot = session.get(Snapshot, snap_a)
        snapshot.state = "ready"
        session.flush()
        session.get(Repository, a).active_snapshot_id = snap_a
        job, run = enqueue(session, a, "question", {"question": "source"}, "test-run")
        run_id = run.id
    with pytest.raises(IntegrityError), SessionLocal.begin() as session:
        session.add(
            RunEvidence(
                run_id=run_id,
                repository_id=a,
                snapshot_id=snap_a,
                evidence_id="e1",
                source_version_id=source_b,
                path="source.py",
                start_line=1,
                end_line=1,
                excerpt="x = 1",
            )
        )
        session.flush()


def test_ready_snapshot_and_source_cannot_be_rewritten(database):
    _, _, _, snap_b, source_b = seed_boundaries()
    with pytest.raises(IntegrityError), SessionLocal.begin() as session:
        session.get(Snapshot, snap_b).commit_sha = "c" * 40
        session.flush()
    with pytest.raises(IntegrityError), SessionLocal.begin() as session:
        session.get(SourceVersion, source_b).content = "replacement"
        session.flush()
