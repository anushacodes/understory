from datetime import timedelta

from app.db import SessionLocal
from app.maintenance import cleanup
from app.models import Job, JobEvent, Repository, Snapshot, SourceVersion
from sqlalchemy import func, select
from test_api import imported


def test_retention_expires_progress_without_deleting_ready_sources(client, config):
    repo_id, job_id = imported(client, config)
    with SessionLocal.begin() as session:
        job = session.get(Job, job_id)
        job.finished_at = session.scalar(select(func.now())) - timedelta(days=8)
        stale = Snapshot(repository_id=repo_id, commit_sha="f" * 40, config_hash="orphan", config={})
        stale.created_at = job.finished_at
        session.add(stale)
        session.flush()
        stale_id = stale.id
    with SessionLocal.begin() as session:
        result = cleanup(session)
        assert result["expired_events"] > 1
        assert result["staging_snapshots"] == 1
    assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "succeeded"
    response = client.get(f"/v1/jobs/{job_id}/events", headers={"Last-Event-ID": "1"})
    assert response.status_code == 410
    with SessionLocal() as session:
        assert session.get(Snapshot, stale_id) is None
        assert session.get(Repository, repo_id).active_snapshot_id
        assert session.scalar(select(func.count()).select_from(SourceVersion)) > 0
        assert session.scalar(select(func.count()).select_from(JobEvent)) == 0


def test_purge_preserves_other_repository(client, config):
    repo_id, _ = imported(client, config)
    with SessionLocal.begin() as session:
        other = Repository(name="other/retained")
        session.add(other)
        session.flush()
        other_id = other.id
    assert client.delete(f"/v1/repositories/{repo_id}").status_code == 200
    assert client.get(f"/v1/repositories/{other_id}").status_code == 200
