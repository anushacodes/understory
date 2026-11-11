"""Explicit local retention cleanup; ready snapshots and saved runs never expire."""

import json
from datetime import timedelta

from sqlalchemy import delete, func, select, text, update

from app.db import SessionLocal
from app.jobs import TERMINAL
from app.models import (
    AnswerRun,
    Embedding,
    Job,
    JobEvent,
    Passage,
    Repository,
    Snapshot,
    SnapshotFile,
    SourceVersion,
)


def cleanup(session):
    session.execute(text("SELECT pg_advisory_xact_lock(781341001)"))
    # Imports serialize their batches on these same repository locks.
    session.execute(select(Repository).order_by(Repository.id).with_for_update()).all()
    cutoff = session.scalar(select(func.now())) - timedelta(days=7)
    terminal_jobs = select(Job.id).where(Job.status.in_(TERMINAL), Job.finished_at < cutoff)
    events = session.execute(delete(JobEvent).where(JobEvent.job_id.in_(terminal_jobs))).rowcount
    candidates = session.scalars(
        select(Snapshot.id).where(
            Snapshot.state != "ready",
            Snapshot.created_at < cutoff,
            ~Snapshot.id.in_(select(AnswerRun.snapshot_id)),
            ~Snapshot.id.in_(
                select(Job.snapshot_id).where(
                    Job.snapshot_id.is_not(None), (Job.status.not_in(TERMINAL)) | (Job.finished_at >= cutoff)
                )
            ),
        )
    ).all()
    session.execute(update(Job).where(Job.snapshot_id.in_(candidates)).values(snapshot_id=None))
    snapshots = session.execute(delete(Snapshot).where(Snapshot.id.in_(candidates))).rowcount
    sources = session.execute(
        delete(SourceVersion).where(
            ~SourceVersion.id.in_(
                select(SnapshotFile.source_version_id).where(SnapshotFile.source_version_id.is_not(None))
            )
        )
    ).rowcount
    vectors = session.execute(
        delete(Embedding).where(
            ~Embedding.key.in_(select(Passage.embedding_key).where(Passage.embedding_key.is_not(None)))
        )
    ).rowcount
    return {
        "expired_events": events,
        "staging_snapshots": snapshots,
        "unreferenced_sources": sources,
        "unused_vectors": vectors,
    }


def main():
    with SessionLocal.begin() as session:
        result = cleanup(session)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
