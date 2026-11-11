import hashlib
import json
from datetime import timedelta

from sqlalchemy import and_, func, or_, select, text

from app.config import settings
from app.db import SessionLocal
from app.errors import AppError, Cancelled, LostLease
from app.models import AnswerRun, Job, JobEvent, Repository, Snapshot

TERMINAL = {"succeeded", "failed", "cancelled"}


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def emit(session, job: Job, event: str, **payload):
    job.event_sequence += 1
    session.add(
        JobEvent(
            job_id=job.id,
            sequence=job.event_sequence,
            event=event,
            payload={"stage": job.stage, "status": job.status, **payload},
        )
    )


def repository(session, repository_id: str) -> Repository:
    repo = session.get(Repository, repository_id)
    if not repo or repo.owner_scope != "owner":
        raise AppError("not_found", "Repository not found.", 404)
    return repo


def ready_snapshot(session, repository_id: str, snapshot_id: str | None = None) -> Snapshot:
    repo = repository(session, repository_id)
    target = snapshot_id or repo.active_snapshot_id
    if not target:
        raise AppError("snapshot_not_ready", "Import a repository before searching or asking questions.", 409)
    snapshot = session.get(Snapshot, target)
    if not snapshot or snapshot.repository_id != repo.id:
        raise AppError("not_found", "Snapshot not found.", 404)
    if snapshot.state != "ready":
        raise AppError("snapshot_not_ready", "This snapshot is not ready.", 409)
    return snapshot


def enqueue(session, repository_id: str, kind: str, request: dict, key: str) -> tuple[Job, AnswerRun | None]:
    # Serialize owner capacity and idempotency checks across repositories.
    session.execute(text("SELECT pg_advisory_xact_lock(781341001)"))
    repo = repository(session, repository_id)
    existing = session.scalar(
        select(Job).where(
            Job.owner_scope == "owner",
            Job.repository_id == repo.id,
            Job.kind == kind,
            Job.idempotency_key == key,
        )
    )
    request_hash = digest(request)
    if existing:
        if existing.request_hash != request_hash:
            raise AppError(
                "idempotency_conflict", "This idempotency key was already used with different input.", 409
            )
        return existing, session.scalar(select(AnswerRun).where(AnswerRun.job_id == existing.id))
    pending = session.scalar(
        select(func.count()).select_from(Job).where(Job.owner_scope == "owner", Job.status.not_in(TERMINAL))
    )
    if pending >= 10:
        raise AppError("queue_capacity", "The work queue is full. Wait for a job to finish.", 429, True)
    generation = None
    snapshot = None
    if kind == "import":
        active = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.repository_id == repo.id, Job.kind == "import", Job.status.not_in(TERMINAL))
        )
        if active >= 2:
            raise AppError(
                "import_capacity", "Two imports are already pending for this repository.", 429, True
            )
        repo = session.scalar(select(Repository).where(Repository.id == repo.id).with_for_update())
        repo.generation += 1
        generation = repo.generation
    else:
        snapshot = ready_snapshot(session, repo.id, request.get("snapshot_id"))
        if snapshot.coverage.get("empty"):
            raise AppError("empty_corpus", "This snapshot has no supported evidence for generation.", 409)
    job = Job(
        repository_id=repo.id,
        kind=kind,
        request=request,
        request_hash=request_hash,
        idempotency_key=key,
        generation=generation,
        snapshot_id=snapshot.id if snapshot else None,
    )
    session.add(job)
    session.flush()
    run = None
    if snapshot:
        run = AnswerRun(
            repository_id=repo.id,
            snapshot_id=snapshot.id,
            job_id=job.id,
            kind=kind,
            question=request.get(
                "question", "Explain this repository's purpose, main modules, and entry points."
            ),
        )
        session.add(run)
        session.flush()
    emit(session, job, "queued")
    return job, run


def claim(config=settings) -> tuple[str, int] | None:
    with SessionLocal.begin() as session:
        now = session.scalar(select(func.now()))
        eligible = or_(
            Job.status == "queued",
            and_(Job.status == "retry_wait", Job.retry_at <= now),
            and_(Job.status == "running", Job.lease_until <= now),
        )
        job = session.scalar(
            select(Job)
            .where(eligible)
            .order_by(Job.created_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        if job.cancel_requested or job.attempt >= config.max_attempts:
            job.status = "cancelled" if job.cancel_requested else "failed"
            job.error = (
                {"code": "attempts_exhausted", "message": "Worker recovery attempts exhausted."}
                if not job.cancel_requested
                else None
            )
            job.finished_at = now
            emit(session, job, job.status)
            return None
        job.attempt += 1
        job.lease_token += 1
        job.status = "running"
        job.lease_until = now + timedelta(seconds=config.lease_seconds)
        job.heartbeat_at = now
        emit(session, job, "claimed", attempt=job.attempt)
        return job.id, job.lease_token


def guard(session, job_id: str, token: int, *, check_cancel: bool = True) -> Job:
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    now = session.scalar(select(func.now()))
    if (
        not job
        or job.status != "running"
        or job.lease_token != token
        or not job.lease_until
        or job.lease_until <= now
    ):
        raise LostLease()
    if check_cancel and job.cancel_requested:
        raise Cancelled()
    return job


def heartbeat(job_id: str, token: int, config=settings):
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token)
        now = session.scalar(select(func.now()))
        job.heartbeat_at = now
        job.lease_until = now + timedelta(seconds=config.lease_seconds)


def checkpoint(job_id: str, token: int, stage: str, **values):
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token)
        job.stage = stage
        job.checkpoint = {**job.checkpoint, **values}
        emit(session, job, "progress", **values)


def settle_error(job_id: str, token: int, error: Exception, config=settings):
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token, check_cancel=False)
        now = session.scalar(select(func.now()))
        if isinstance(error, Cancelled) or job.cancel_requested:
            job.status = "cancelled"
        else:
            app_error = (
                error
                if isinstance(error, AppError)
                else AppError(
                    "internal_error", "The job failed unexpectedly. Check the worker diagnostics.", 500
                )
            )
            job.error = {
                "code": app_error.code,
                "message": app_error.message,
                "retryable": app_error.retryable,
            }
            if app_error.retryable and job.attempt < config.max_attempts:
                job.status = "retry_wait"
                job.retry_at = now + timedelta(seconds=min(60, 2**job.attempt))
            else:
                job.status = "failed"
        if job.status in TERMINAL:
            job.finished_at = now
        job.lease_until = None
        emit(session, job, job.status, error=job.error)
