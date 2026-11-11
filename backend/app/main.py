import asyncio
import hmac
import json
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors import canonical_repository
from app.db import SessionLocal, engine, get_session
from app.errors import AppError
from app.jobs import TERMINAL, emit, enqueue, ready_snapshot, repository
from app.middleware import BodyLimitMiddleware
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
    Symbol,
    WorkerPresence,
)
from app.retrieval import search, source_url
from app.schemas import ImportInput, OverviewInput, QuestionInput, RepositoryInput

app = FastAPI(title="Understory", version="0.1.0", docs_url="/api-docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID"],
    expose_headers=["X-Request-ID"],
)
bearer = HTTPBearer(auto_error=False)
app.add_middleware(BodyLimitMiddleware)


def owner(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if (
        not settings.owner_token
        or not credentials
        or not hmac.compare_digest(credentials.credentials, settings.owner_token)
    ):
        raise AppError("unauthorized", "Enter the owner token configured in the server's .env file.", 401)
    return "owner"


DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[str, Depends(owner)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, error: AppError):
    return JSONResponse(
        {
            "error": {"code": error.code, "message": error.message, "retryable": error.retryable},
            "request_id": request.state.request_id,
        },
        status_code=error.status,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, error: RequestValidationError):
    return JSONResponse(
        {
            "error": {
                "code": "invalid_input",
                "message": "Check the request fields and configured input limits.",
                "retryable": False,
            },
            "request_id": request.state.request_id,
        },
        status_code=422,
    )


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, error: SQLAlchemyError):
    return JSONResponse(
        {
            "error": {
                "code": "database_unavailable",
                "message": "Database operation failed. Check the local database and migrations.",
                "retryable": True,
            },
            "request_id": request.state.request_id,
        },
        status_code=503,
    )


def repository_json(repo: Repository, session) -> dict:
    snapshot = session.get(Snapshot, repo.active_snapshot_id) if repo.active_snapshot_id else None
    return {
        "id": repo.id,
        "name": repo.name,
        "default_ref": repo.default_ref,
        "active_snapshot_id": repo.active_snapshot_id,
        "commit_sha": snapshot.commit_sha if snapshot else None,
        "coverage": snapshot.coverage if snapshot else None,
        "created_at": repo.created_at.isoformat(),
        "synthetic": repo.name == "understory/fixture",
    }


def job_json(job: Job) -> dict:
    return {
        "id": job.id,
        "repository_id": job.repository_id,
        "kind": job.kind,
        "status": job.status,
        "stage": job.stage,
        "attempt": job.attempt,
        "commit_sha": job.resolved_sha,
        "snapshot_id": job.snapshot_id,
        "checkpoint": job.checkpoint,
        "result": job.result,
        "error": job.error,
        "cancel_requested": job.cancel_requested,
        "last_event_id": job.event_sequence,
        "heartbeat_at": job.heartbeat_at,
        "retry_at": job.retry_at,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def get_job(session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job or job.owner_scope != "owner":
        raise AppError("not_found", "Job not found.", 404)
    repository(session, job.repository_id)
    return job


def accepted(job: Job, run: AnswerRun | None):
    result = {
        "job_id": job.id,
        "status": job.status,
        "snapshot_id": job.snapshot_id,
        "status_url": f"/v1/jobs/{job.id}",
        "events_url": f"/v1/jobs/{job.id}/events",
    }
    if run:
        result.update({"run_id": run.id, "result_url": f"/v1/runs/{run.id}"})
    return result


@app.get("/v1/health")
def health():
    return {"status": "ok"}


@app.get("/v1/ready")
def ready():
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0004":
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable"}, status_code=503)


@app.get("/v1/settings")
def capabilities(identity: Owner):
    return {
        "generation_enabled": settings.generation_provider == "groq"
        and bool(settings.groq_api_key)
        and settings.daily_token_budget > 0,
        "generation_provider": settings.generation_provider,
        "embedding_provider": settings.embedding_provider,
        "allowed_repositories": settings.allowed_repositories,
        "synthetic_fixture": "understory/fixture",
    }


@app.post("/v1/repositories")
def register(body: RepositoryInput, identity: Owner, session: DB):
    name = canonical_repository(body.github_repository)
    if name not in settings.allowed_repositories:
        raise AppError(
            "repository_not_allowed",
            "Add this public repository to ALLOWED_REPOSITORIES in the server's .env file before importing it.",
        )
    existing = session.scalar(
        select(Repository).where(Repository.owner_scope == identity, Repository.name == name)
    )
    if existing:
        return repository_json(existing, session)
    repo = Repository(name=name, default_ref=body.default_ref)
    session.add(repo)
    session.commit()
    return JSONResponse(repository_json(repo, session), status_code=201)


@app.get("/v1/repositories")
def list_repositories(identity: Owner, session: DB, limit: int = Query(20, ge=1, le=100), cursor: str = ""):
    rows = session.scalars(
        select(Repository)
        .where(Repository.owner_scope == identity, Repository.id > cursor)
        .order_by(Repository.id)
        .limit(limit + 1)
    ).all()
    return {
        "items": [repository_json(repo, session) for repo in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


@app.get("/v1/repositories/{repository_id}")
def get_repository(repository_id: str, identity: Owner, session: DB):
    repo = repository(session, repository_id)
    jobs = session.scalars(
        select(Job).where(Job.repository_id == repo.id).order_by(Job.created_at.desc()).limit(10)
    ).all()
    from datetime import timedelta

    now = session.scalar(select(func.now()))
    observed = session.scalar(select(func.max(WorkerPresence.observed_at)))
    return {
        **repository_json(repo, session),
        "jobs": [job_json(job) for job in jobs],
        "worker": {
            "available": bool(observed and now - observed < timedelta(seconds=45)),
            "heartbeat_at": observed,
        },
    }


@app.post("/v1/repositories/{repository_id}/imports", status_code=202)
def queue_import(repository_id: str, body: ImportInput, key: Key, identity: Owner, session: DB):
    repo = repository(session, repository_id)
    if repo.name not in settings.allowed_repositories:
        raise AppError("repository_not_allowed", "This repository is no longer allowlisted.")
    job, run = enqueue(session, repository_id, "import", body.model_dump(), key)
    session.commit()
    return accepted(job, run)


@app.get("/v1/repositories/{repository_id}/snapshots")
def list_snapshots(
    repository_id: str, identity: Owner, session: DB, limit: int = Query(20, ge=1, le=100), cursor: str = ""
):
    repository(session, repository_id)
    rows = session.scalars(
        select(Snapshot)
        .where(Snapshot.repository_id == repository_id, Snapshot.state == "ready", Snapshot.id > cursor)
        .order_by(Snapshot.id)
        .limit(limit + 1)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "commit_sha": item.commit_sha,
                "coverage": item.coverage,
                "ready_at": item.ready_at,
                "config": item.config,
            }
            for item in rows[:limit]
        ],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


@app.get("/v1/repositories/{repository_id}/tree")
def tree(
    repository_id: str,
    identity: Owner,
    session: DB,
    snapshot_id: str | None = None,
    directory: str = "",
    limit: int = Query(100, ge=1, le=100),
    cursor: str = "",
):
    snapshot = ready_snapshot(session, repository_id, snapshot_id)
    rows = session.execute(
        select(SnapshotFile, SourceVersion.kind)
        .outerjoin(SourceVersion, SourceVersion.id == SnapshotFile.source_version_id)
        .where(
            SnapshotFile.snapshot_id == snapshot.id,
            SnapshotFile.path.startswith(directory, autoescape=True),
            SnapshotFile.path > cursor,
        )
        .order_by(SnapshotFile.path)
        .limit(limit + 1)
    ).all()
    return {
        "snapshot_id": snapshot.id,
        "commit_sha": snapshot.commit_sha,
        "coverage": snapshot.coverage,
        "items": [
            {"path": f.path, "kind": kind, "state": f.state, "reason": f.reason, "byte_count": f.byte_count}
            for f, kind in rows[:limit]
        ],
        "next_cursor": rows[limit - 1][0].path if len(rows) > limit else None,
    }


@app.get("/v1/repositories/{repository_id}/files")
def read_file(
    repository_id: str,
    identity: Owner,
    session: DB,
    path: str,
    snapshot_id: str | None = None,
    start_line: int = Query(1, ge=1),
    end_line: int | None = Query(None, ge=1),
):
    snapshot = ready_snapshot(session, repository_id, snapshot_id)
    repo = repository(session, repository_id)
    file = session.scalar(
        select(SnapshotFile).where(SnapshotFile.snapshot_id == snapshot.id, SnapshotFile.path == path)
    )
    if not file:
        raise AppError("not_found", "This path does not exist in the selected snapshot.", 404)
    if not file.source_version_id:
        raise AppError("source_excluded", f"Source body was excluded: {file.reason}.", 409)
    source = session.get(SourceVersion, file.source_version_id)
    end = min(end_line or start_line + 299, source.line_count)
    if start_line > max(1, source.line_count) or end < start_line - 1 or end - start_line >= 300:
        raise AppError("invalid_range", "Choose an existing range of at most 300 lines.")
    lines = source.content.splitlines()[start_line - 1 : end]
    content = "\n".join(lines)
    if len(content.encode()) > 256 * 1024:
        raise AppError("source_range_too_large", "Choose fewer source lines; this response exceeds 256 KiB.")
    return {
        "snapshot_id": snapshot.id,
        "commit_sha": snapshot.commit_sha,
        "source_version_id": source.id,
        "path": path,
        "kind": source.kind,
        "state": file.state,
        "start_line": start_line,
        "end_line": end,
        "line_count": source.line_count,
        "content": content,
        "next_start_line": end + 1 if end < source.line_count else None,
        "source_url": source_url(repo.name, snapshot.commit_sha, path, start_line, max(start_line, end)),
    }


@app.get("/v1/repositories/{repository_id}/symbols")
def symbols(
    repository_id: str,
    identity: Owner,
    session: DB,
    snapshot_id: str | None = None,
    query: str = Query("", max_length=2000),
    path: str | None = None,
    exact: bool = False,
    limit: int = Query(20, ge=1, le=100),
    cursor: str = "",
):
    snapshot = ready_snapshot(session, repository_id, snapshot_id)
    statement = (
        select(Symbol, SourceVersion.path)
        .join(SourceVersion)
        .join(SnapshotFile, SnapshotFile.source_version_id == SourceVersion.id)
        .where(
            SnapshotFile.snapshot_id == snapshot.id,
            Symbol.id > cursor,
            Symbol.parser == snapshot.config["parser"],
        )
    )
    if query:
        statement = statement.where(
            ((Symbol.name == query) | (Symbol.qualified_name == query))
            if exact
            else (
                Symbol.name.startswith(query, autoescape=True)
                | Symbol.qualified_name.startswith(query, autoescape=True)
            )
        )
    if path:
        statement = statement.where(SourceVersion.path == path)
    rows = session.execute(statement.order_by(Symbol.id).limit(limit + 1)).all()
    return {
        "snapshot_id": snapshot.id,
        "items": [
            {
                "id": symbol.id,
                "path": source_path,
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "kind": symbol.kind,
                "parent": symbol.parent,
                "start_line": symbol.start_line,
                "end_line": symbol.end_line,
            }
            for symbol, source_path in rows[:limit]
        ],
        "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None,
    }


@app.get("/v1/repositories/{repository_id}/search")
def search_sources(
    repository_id: str,
    identity: Owner,
    session: DB,
    query: str = Query(min_length=1, max_length=2000),
    snapshot_id: str | None = None,
    mode: str = "lexical",
    kinds: Annotated[list[str] | None, Query()] = None,
    path_prefix: str = "",
    limit: int = Query(10, ge=1, le=20),
    allow_lexical_fallback: bool = False,
):
    return search(
        session, repository_id, query, snapshot_id, mode, kinds, path_prefix, limit, allow_lexical_fallback
    )


@app.post("/v1/repositories/{repository_id}/questions", status_code=202)
def queue_question(repository_id: str, body: QuestionInput, key: Key, identity: Owner, session: DB):
    job, run = enqueue(session, repository_id, "question", body.model_dump(), key)
    session.commit()
    return accepted(job, run)


@app.post("/v1/repositories/{repository_id}/overviews", status_code=202)
def queue_overview(repository_id: str, body: OverviewInput, key: Key, identity: Owner, session: DB):
    job, run = enqueue(session, repository_id, "overview", body.model_dump(), key)
    session.commit()
    return accepted(job, run)


@app.get("/v1/repositories/{repository_id}/runs")
def run_history(
    repository_id: str, identity: Owner, session: DB, limit: int = Query(20, ge=1, le=100), cursor: str = ""
):
    repository(session, repository_id)
    rows = session.scalars(
        select(AnswerRun)
        .where(AnswerRun.repository_id == repository_id, AnswerRun.id > cursor)
        .order_by(AnswerRun.id)
        .limit(limit + 1)
    ).all()
    return {
        "items": [
            {
                "id": run.id,
                "job_id": run.job_id,
                "kind": run.kind,
                "question": run.question,
                "snapshot_id": run.snapshot_id,
                "created_at": run.created_at,
            }
            for run in rows[:limit]
        ],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


def run_result(session, run_id: str):
    run = session.get(AnswerRun, run_id)
    if not run:
        raise AppError("not_found", "Answer run not found.", 404)
    repository(session, run.repository_id)
    job = get_job(session, run.job_id)
    return {
        "id": run.id,
        "repository_id": run.repository_id,
        "snapshot_id": run.snapshot_id,
        "kind": run.kind,
        "question": run.question,
        "job": job_json(job),
        "config": run.config,
        "evidence": run.evidence,
        "output": run.output,
        "created_at": run.created_at,
    }


@app.get("/v1/runs/{run_id}")
def get_run(run_id: str, identity: Owner, session: DB):
    return run_result(session, run_id)


@app.get("/v1/runs/{run_id}/export")
def export_run(run_id: str, identity: Owner, session: DB):
    result = run_result(session, run_id)
    return {"schema_version": 1, **result}


@app.get("/v1/jobs/{job_id}")
def read_job(job_id: str, identity: Owner, session: DB):
    return job_json(get_job(session, job_id))


@app.post("/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str, identity: Owner, session: DB):
    get_job(session, job_id)
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job.status not in TERMINAL:
        job.cancel_requested = True
        if job.status in {"queued", "retry_wait"}:
            job.status = "cancelled"
            job.finished_at = session.scalar(select(func.now()))
        emit(session, job, "cancellation_requested")
    session.commit()
    from fastapi.encoders import jsonable_encoder

    return JSONResponse(jsonable_encoder(job_json(job)), status_code=200 if job.status in TERMINAL else 202)


@app.get("/v1/jobs/{job_id}/events")
async def events(
    job_id: str, identity: Owner, request: Request, last_event_id: Annotated[str | None, Header()] = None
):
    try:
        after = int(last_event_id or 0)
        if after < 0:
            raise ValueError()
    except ValueError as exc:
        raise AppError("invalid_event_cursor", "Last-Event-ID must be a nonnegative event sequence.") from exc
    with SessionLocal() as session:
        get_job(session, job_id)
        first = session.scalar(select(func.min(JobEvent.sequence)).where(JobEvent.job_id == job_id))
        if after and first and after < first - 1:
            raise AppError(
                "event_history_expired", "Reload job state to reset the expired event cursor.", 410
            )

    async def stream():
        cursor = after
        while not await request.is_disconnected():
            with SessionLocal() as session:
                job = get_job(session, job_id)
                rows = session.scalars(
                    select(JobEvent)
                    .where(JobEvent.job_id == job_id, JobEvent.sequence > cursor)
                    .order_by(JobEvent.sequence)
                    .limit(100)
                ).all()
                terminal = job.status in TERMINAL
            for item in rows:
                cursor = item.sequence
                yield f"id: {item.sequence}\nevent: {item.event}\ndata: {json.dumps(item.payload)}\n\n"
            if terminal and (not rows or cursor >= job.event_sequence):
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(0.75)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/v1/repositories/{repository_id}")
def purge(repository_id: str, identity: Owner, session: DB):
    session.execute(text("SELECT pg_advisory_xact_lock(781341001)"))
    repo = repository(session, repository_id)
    pending = session.scalar(
        select(func.count()).select_from(Job).where(Job.repository_id == repo.id, Job.status.not_in(TERMINAL))
    )
    if pending:
        raise AppError("jobs_pending", "Cancel or finish pending jobs before purging this repository.", 409)
    repo.active_snapshot_id = None
    session.flush()
    session.execute(delete(AnswerRun).where(AnswerRun.repository_id == repo.id))
    session.execute(delete(Job).where(Job.repository_id == repo.id))
    session.delete(repo)
    session.flush()
    session.execute(
        delete(Embedding).where(
            ~Embedding.key.in_(select(Passage.embedding_key).where(Passage.embedding_key.is_not(None)))
        )
    )
    session.commit()
    return {"purged": True, "repository_id": repository_id}


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.api_port, access_log=False)
