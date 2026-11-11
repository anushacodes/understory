"""Recover a genuinely terminated worker against PostgreSQL, not an in-memory fake."""

import os
import subprocess
from datetime import timedelta

from app.db import SessionLocal
from app.jobs import enqueue
from app.models import Job, Passage, Repository, SnapshotFile, SourceVersion
from app.worker import run_once
from sqlalchemy import func, select, text


def test_worker_process_crash_replays_committed_source_batches(database, config):
    schema = database.url  # Credentials remain in process memory; never printed.
    with database.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    with SessionLocal.begin() as session:
        repo = Repository(name="understory/fixture")
        session.add(repo)
        session.flush()
        job, _ = enqueue(session, repo.id, "import", {"ref": "a"}, "crash-recovery")
        job_id, repo_id = job.id, repo.id
    environment = {
        **os.environ,
        "PGOPTIONS": f"-csearch_path={schema},public",
        "EMBEDDING_PROVIDER": "disabled",
        "GENERATION_PROVIDER": "disabled",
        "GROQ_API_KEY": "",
        "DAILY_TOKEN_BUDGET": "0",
    }
    program = """
import os
from app.worker import Lease, run_once
original = Lease.check
calls = 0
def crash_between_batches(self):
    global calls
    calls += 1
    if calls == 6:
        os._exit(73)
    return original(self)
Lease.check = crash_between_batches
run_once()
"""
    child = subprocess.run(
        [str(__import__("pathlib").Path(".venv/bin/python")), "-c", program],
        env=environment,
        timeout=30,
        capture_output=True,
    )
    assert child.returncode == 73
    with SessionLocal.begin() as session:
        job = session.get(Job, job_id)
        assert job.status == "running"
        assert job.checkpoint["files_processed"] >= 2
        assert job.resolved_sha
        pinned_sha = job.resolved_sha
        job.lease_until = session.scalar(select(func.now())) - timedelta(seconds=1)
    assert run_once(config)
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job.status == "succeeded", job.error
        assert job.attempt == 2
        assert job.resolved_sha == pinned_sha
        assert session.get(Repository, repo_id).active_snapshot_id == job.snapshot_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(SnapshotFile)
                .where(SnapshotFile.snapshot_id == job.snapshot_id)
            )
            == 14
        )
        for _model, identity in [
            (SourceVersion, (SourceVersion.path, SourceVersion.content_hash)),
            (
                Passage,
                (
                    Passage.source_version_id,
                    Passage.config_hash,
                    Passage.label,
                    Passage.start_line,
                    Passage.end_line,
                ),
            ),
        ]:
            duplicates = select(*identity).group_by(*identity).having(func.count() > 1)
            assert not session.execute(duplicates).all()
