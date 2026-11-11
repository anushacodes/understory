from datetime import timedelta

import pytest
from app.db import SessionLocal
from app.errors import AppError, LostLease
from app.jobs import checkpoint, claim, enqueue, guard
from app.models import Job, JobEvent, Repository, Snapshot
from app.worker import activate
from sqlalchemy import func, select


def repo_and_job(key="first"):
    with SessionLocal.begin() as session:
        repo = Repository(name="understory/fixture")
        session.add(repo)
        session.flush()
        job, _ = enqueue(session, repo.id, "import", {"ref": "a"}, key)
        return repo.id, job.id


def test_idempotency_replay_and_conflict(database):
    repo_id, job_id = repo_and_job()
    with SessionLocal.begin() as session:
        replay, _ = enqueue(session, repo_id, "import", {"ref": "a"}, "first")
        assert replay.id == job_id
    with SessionLocal.begin() as session, pytest.raises(AppError) as error:
        enqueue(session, repo_id, "import", {"ref": "b"}, "first")
    assert error.value.code == "idempotency_conflict"


def test_reclaimed_lease_rejects_old_worker_writes(database, config):
    _, job_id = repo_and_job()
    assert claim(config) == (job_id, 1)
    checkpoint(job_id, 1, "download", persisted=True)
    with SessionLocal.begin() as session:
        job = session.get(Job, job_id)
        job.lease_until = session.scalar(select(func.now())) - timedelta(seconds=1)
    assert claim(config) == (job_id, 2)
    with pytest.raises(LostLease):
        checkpoint(job_id, 1, "activate", stale=True)
    with SessionLocal.begin() as session, pytest.raises(LostLease):
        guard(session, job_id, 1)
    with SessionLocal() as session:
        assert session.get(Job, job_id).checkpoint == {"persisted": True}
        events = session.scalars(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.sequence)
        ).all()
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))


def test_latest_requested_generation_controls_activation(database, config):
    repo_id, older = repo_and_job()
    assert claim(config) == (older, 1)
    with SessionLocal.begin() as session:
        newer, _ = enqueue(session, repo_id, "import", {"ref": "b"}, "second")
        newer_id = newer.id
        a = Snapshot(repository_id=repo_id, commit_sha="a" * 40, config_hash="a", config={})
        b = Snapshot(repository_id=repo_id, commit_sha="b" * 40, config_hash="b", config={})
        session.add_all([a, b])
        session.flush()
        a_id, b_id = a.id, b.id
    assert claim(config) == (newer_id, 1)
    activate(newer_id, 1, b_id)
    activate(older, 1, a_id)
    with SessionLocal() as session:
        assert session.get(Repository, repo_id).active_snapshot_id == b_id
        assert session.get(Job, older).result["reason"] == "superseded"
        assert session.get(Snapshot, a_id).state == "ready"


def test_queue_capacity_is_enforced(database):
    repo_id, _ = repo_and_job()
    with SessionLocal.begin() as session:
        enqueue(session, repo_id, "import", {"ref": "b"}, "second")
    with SessionLocal.begin() as session, pytest.raises(AppError) as error:
        enqueue(session, repo_id, "import", {"ref": "main"}, "third")
    assert error.value.code == "import_capacity"
