from app.db import SessionLocal
from app.jobs import enqueue
from app.models import Job, Passage, Repository, Snapshot, SnapshotFile, SourceVersion
from app.retrieval import search
from app.worker import run_once
from sqlalchemy import func, select


def add_repo():
    with SessionLocal.begin() as session:
        repo = Repository(name="understory/fixture")
        session.add(repo)
        session.flush()
        return repo.id


def import_ref(repo_id, ref, config, key=None):
    with SessionLocal.begin() as session:
        job, _ = enqueue(session, repo_id, "import", {"ref": ref}, key or "import-" + ref)
        job_id = job.id
    assert run_once(config)
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job.status == "succeeded", job.error
        return job.result["snapshot_id"]


def test_import_search_ranges_and_skipped_inventory(database, config):
    repo_id = add_repo()
    snapshot_id = import_ref(repo_id, "a", config)
    with SessionLocal() as session:
        snapshot = session.get(Snapshot, snapshot_id)
        assert snapshot.coverage["synthetic"] is True
        assert snapshot.coverage["included_files"] > 10
        assert snapshot.coverage["excluded_files"] == 2
        result = search(session, repo_id, "validate_payload", snapshot_id, "exact")
        assert any(hit["path"] == "app/validation.py" for hit in result["results"])
        for hit in result["results"]:
            source = session.get(SourceVersion, hit["source_version_id"])
            assert hit["excerpt"] == "\n".join(
                source.content.splitlines()[hit["start_line"] - 1 : hit["end_line"]]
            )
            assert hit["source_url"] is None  # synthetic inputs never claim a real GitHub URL


def test_same_sha_reimport_does_not_duplicate_rows(database, config):
    repo_id = add_repo()
    first = import_ref(repo_id, "a", config)
    with SessionLocal() as session:
        counts = [
            session.scalar(select(func.count()).select_from(model))
            for model in (SourceVersion, Passage, SnapshotFile)
        ]
    second = import_ref(repo_id, "a", config, "new-request")
    assert first == second
    with SessionLocal() as session:
        assert counts == [
            session.scalar(select(func.count()).select_from(model))
            for model in (SourceVersion, Passage, SnapshotFile)
        ]


def test_b_refresh_removes_renames_and_retains_a(database, config):
    repo_id = add_repo()
    a = import_ref(repo_id, "a", config)
    b = import_ref(repo_id, "b", config)
    with SessionLocal() as session:

        def paths(snapshot):
            return set(
                session.scalars(select(SnapshotFile.path).where(SnapshotFile.snapshot_id == snapshot)).all()
            )

        assert "app/legacy.py" in paths(a) and "app/legacy.py" not in paths(b)
        assert "app/formatting.py" in paths(a) and "app/display.py" in paths(b)
        assert session.get(Repository, repo_id).active_snapshot_id == b
        old = search(session, repo_id, "positive integer", a, "lexical")
        new = search(session, repo_id, "1_000_000", b, "lexical")
        assert old["commit_sha"] != new["commit_sha"]
        assert all(hit["path"] != "app/legacy.py" for hit in new["results"])


def test_failed_refresh_preserves_previous_snapshot(database, config):
    repo_id = add_repo()
    active = import_ref(repo_id, "a", config)
    with SessionLocal.begin() as session:
        job, _ = enqueue(session, repo_id, "import", {"ref": "unknown"}, "bad-ref")
        job_id = job.id
    run_once(config)
    with SessionLocal() as session:
        assert session.get(Job, job_id).status == "failed"
        assert session.get(Repository, repo_id).active_snapshot_id == active
