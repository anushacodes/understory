import logging
import signal
import threading
import time

from sqlalchemy import delete, func, select, text

from app.config import settings
from app.connectors import connector, safe_archive
from app.db import SessionLocal
from app.errors import AppError, Cancelled, LostLease
from app.indexing import content_hash, parse
from app.jobs import checkpoint, claim, digest, emit, guard, heartbeat, settle_error, worker_presence
from app.models import (
    AnswerRun,
    Embedding,
    Job,
    Passage,
    Repository,
    RunEvidence,
    Snapshot,
    SnapshotFile,
    SourceVersion,
    Symbol,
    UsageEvent,
)
from app.providers import embed, embedding_identity, embedding_input, embedding_key, generate
from app.retrieval import search, source_url

logger = logging.getLogger("understory.worker")


class Lease:
    def __init__(self, job_id, token, config=settings):
        self.job_id, self.token, self.config = job_id, token, config
        self.stop = threading.Event()
        self.error = None
        self.started = time.monotonic()
        with SessionLocal() as session:
            self.prior_seconds = session.get(Job, job_id).execution_seconds

    def check(self):
        if self.error:
            raise self.error
        with SessionLocal() as session:
            job = session.get(Job, self.job_id)
            deadline = 900 if job.kind == "import" else 90
        if self.prior_seconds + time.monotonic() - self.started > deadline:
            raise AppError("deadline_exceeded", "Job execution deadline exceeded.")

    def renew(self):
        while not self.stop.wait(self.config.heartbeat_seconds):
            try:
                heartbeat(self.job_id, self.token, self.config)
                worker_presence()
            except Exception as exc:
                self.error = exc
                break

    def __enter__(self):
        self.thread = threading.Thread(target=self.renew, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=2)


def import_repository(job_id: str, token: int, config, lease):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        name = session.get(Repository, job.repository_id).name
        request = job.request
        sha = job.resolved_sha
    source = connector(name, config)
    if name not in config.allowed_repositories:
        raise AppError("repository_not_allowed", "This repository is no longer approved for imports.")

    def count_request():
        with SessionLocal.begin() as session:
            current = guard(session, job_id, token)
            count = int(current.checkpoint.get("github_requests", 0)) + 1
            if count > 20:
                raise AppError("github_budget", "GitHub request budget exhausted across import attempts.")
            current.checkpoint = {**current.checkpoint, "github_requests": count}
            emit(session, current, "github_request", attempted_requests=count)

    source.on_request = count_request
    checkpoint(job_id, token, "resolve")
    if not sha:
        sha = source.resolve(name, request["ref"])
        with SessionLocal.begin() as session:
            job = guard(session, job_id, token)
            repo = session.scalar(
                select(Repository).where(Repository.id == job.repository_id).with_for_update()
            )
            if source.provider_id:
                if repo.provider_id and repo.provider_id != source.provider_id:
                    raise AppError(
                        "repository_identity_changed",
                        "The allowlisted repository name now identifies a different provider object.",
                    )
                repo.provider_id = source.provider_id
            job.resolved_sha = sha
            emit(session, job, "source_pinned", commit_sha=sha)
    elif hasattr(source, "identify"):
        current_provider_id = source.identify(name)
        with SessionLocal() as session:
            if session.get(Repository, job.repository_id).provider_id != current_provider_id:
                raise AppError(
                    "repository_identity_changed", "Pinned repository identity changed; retry is refused."
                )
    identity = embedding_identity(config)
    index_config = {**config.indexing_config(), "embedding": identity}
    config_hash = digest(index_config)
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token)
        # Serialize duplicate builds on repository lock; never hold it across network work.
        session.execute(select(Repository).where(Repository.id == job.repository_id).with_for_update())
        snapshot = session.scalar(
            select(Snapshot).where(
                Snapshot.repository_id == job.repository_id,
                Snapshot.commit_sha == sha,
                Snapshot.config_hash == config_hash,
            )
        )
        if snapshot is None:
            snapshot = Snapshot(
                repository_id=job.repository_id, commit_sha=sha, config_hash=config_hash, config=index_config
            )
            session.add(snapshot)
            session.flush()
        if snapshot.state != "ready":
            builder = session.scalar(
                select(Job.id)
                .where(
                    Job.snapshot_id == snapshot.id,
                    Job.id != job_id,
                    Job.status == "running",
                    Job.lease_until > func.now(),
                )
                .limit(1)
            )
            if builder:
                raise AppError(
                    "snapshot_build_busy",
                    "A current worker is building this same snapshot. This job will retry after the lease interval.",
                    503,
                    True,
                    retry_after=config.lease_seconds,
                )
        job.snapshot_id = snapshot.id
        snapshot_id, already_ready = snapshot.id, snapshot.state == "ready"
    if already_ready:
        activate(job_id, token, snapshot_id)
        return
    checkpoint(job_id, token, "download", commit_sha=sha)
    data = source.download(name, sha)
    lease.check()
    checkpoint(job_id, token, "inventory", archive_bytes=len(data))
    files = safe_archive(data, config)
    counters = {
        "total_files": len(files),
        "included_files": 0,
        "excluded_files": 0,
        "parse_failed_files": 0,
        "passages": 0,
        "symbols": 0,
        "reused_embeddings": 0,
        "supported_bytes": 0,
        "synthetic": name == "understory/fixture",
    }
    for n, file in enumerate(files, 1):
        lease.check()
        parsed = parse(file.path, file.content, file.kind) if file.content is not None else None
        if file.content is None:
            state, reason = "excluded", file.reason
            counters["excluded_files"] += 1
        elif parsed.error:
            state, reason = "parse_failed", parsed.error
            counters["parse_failed_files"] += 1
        else:
            state, reason = "included", None
            counters["included_files"] += 1
            counters["supported_bytes"] += file.size
            counters["passages"] += len(parsed.passages)
            counters["symbols"] += len(parsed.symbols)
        with SessionLocal.begin() as session:
            job = guard(session, job_id, token)
            # Prevent concurrent same-source writes across snapshot/configuration jobs.
            session.execute(select(Repository).where(Repository.id == job.repository_id).with_for_update())
            source_version = None
            if file.content is not None:
                content_digest = content_hash(file.content.encode())
                source_version = session.scalar(
                    select(SourceVersion).where(
                        SourceVersion.repository_id == job.repository_id,
                        SourceVersion.path == file.path,
                        SourceVersion.content_hash == content_digest,
                    )
                )
                if source_version is None:
                    stored = session.scalar(select(func.coalesce(func.sum(SourceVersion.byte_count), 0)))
                    if stored + file.size > config.storage_limit:
                        raise AppError(
                            "storage_limit",
                            "Local source storage ceiling reached. Export and purge an unused repository before importing.",
                        )
                    source_version = SourceVersion(
                        repository_id=job.repository_id,
                        path=file.path,
                        content_hash=content_digest,
                        content=file.content,
                        kind=file.kind,
                        line_count=len(file.content.splitlines()),
                        byte_count=file.size,
                    )
                    session.add(source_version)
                    session.flush()
            membership = session.scalar(
                select(SnapshotFile).where(
                    SnapshotFile.snapshot_id == snapshot_id, SnapshotFile.path == file.path
                )
            )
            if membership is None:
                session.add(
                    SnapshotFile(
                        snapshot_id=snapshot_id,
                        path=file.path,
                        source_version_id=source_version.id if source_version else None,
                        byte_count=file.size,
                        state=state,
                        reason=reason,
                    )
                )
            if parsed and not parsed.error:
                for symbol in parsed.symbols:
                    existing = session.scalar(
                        select(Symbol.id).where(
                            Symbol.source_version_id == source_version.id,
                            Symbol.parser == index_config["parser"],
                            Symbol.qualified_name == symbol["qualified_name"],
                            Symbol.start_line == symbol["start_line"],
                        )
                    )
                    if not existing:
                        session.add(
                            Symbol(
                                source_version_id=source_version.id, parser=index_config["parser"], **symbol
                            )
                        )
                for item in parsed.passages:
                    exists = session.scalar(
                        select(Passage.id).where(
                            Passage.source_version_id == source_version.id,
                            Passage.config_hash == config_hash,
                            Passage.label == item["label"],
                            Passage.start_line == item["start_line"],
                            Passage.end_line == item["end_line"],
                        )
                    )
                    if not exists:
                        session.add(
                            Passage(source_version_id=source_version.id, config_hash=config_hash, **item)
                        )
            job.stage = "parse"
            job.checkpoint = {**job.checkpoint, "files_processed": n, **counters}
            emit(session, job, "progress", **job.checkpoint)
    if identity["provider"] != "disabled":
        with SessionLocal() as session:
            rows = session.execute(
                select(Passage.id, SourceVersion.path, Passage.label, Passage.excerpt)
                .join(SourceVersion)
                .join(SnapshotFile, SnapshotFile.source_version_id == SourceVersion.id)
                .where(SnapshotFile.snapshot_id == snapshot_id, Passage.config_hash == config_hash)
            ).all()
        for n, (passage_id, path, label, excerpt) in enumerate(rows, 1):
            lease.check()
            input_text = embedding_input(path, label, excerpt, config)
            key = embedding_key(input_text, identity)
            with SessionLocal() as session:
                cached = session.get(Embedding, key)
            vector = None if cached else embed([input_text], config)[0]
            if cached:
                counters["reused_embeddings"] += 1
            with SessionLocal.begin() as session:
                job = guard(session, job_id, token)
                session.execute(
                    select(Repository).where(Repository.id == job.repository_id).with_for_update()
                )
                if session.get(Embedding, key) is None:
                    session.add(Embedding(key=key, config=identity, dimensions=len(vector), vector=vector))
                    session.flush()
                session.get(Passage, passage_id).embedding_key = key
                job.stage = "embed"
                job.checkpoint = {**job.checkpoint, **counters, "embedded_passages": n}
                emit(session, job, "progress", **job.checkpoint)
    lease.check()
    checkpoint(job_id, token, "validate")
    counters["empty"] = counters["passages"] == 0
    counters["partial"] = counters["excluded_files"] > 0 or counters["parse_failed_files"] > 0
    counters["capabilities"] = ["exact", "lexical"] + (
        ["semantic", "hybrid"] if identity["provider"] != "disabled" else []
    )
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token)
        snapshot = session.get(Snapshot, snapshot_id)
        actual = session.scalar(
            select(func.count()).select_from(SnapshotFile).where(SnapshotFile.snapshot_id == snapshot_id)
        )
        if actual != len(files):
            raise AppError("manifest_mismatch", "Manifest failed completeness validation.")
        rows = session.execute(
            select(Passage, SourceVersion)
            .join(SourceVersion)
            .join(SnapshotFile, SnapshotFile.source_version_id == SourceVersion.id)
            .where(
                SnapshotFile.snapshot_id == snapshot_id,
                SnapshotFile.state == "included",
                Passage.config_hash == config_hash,
            )
        ).all()
        symbols = session.scalars(
            select(Symbol)
            .join(SnapshotFile, SnapshotFile.source_version_id == Symbol.source_version_id)
            .where(
                SnapshotFile.snapshot_id == snapshot_id,
                SnapshotFile.state == "included",
                Symbol.parser == index_config["parser"],
            )
        ).all()
        if len(rows) != counters["passages"] or len(symbols) != counters["symbols"]:
            raise AppError("index_incomplete", "Source placement counts failed validation.")
        for passage, original in rows:
            if not (1 <= passage.start_line <= passage.end_line <= original.line_count) or (
                passage.excerpt
                != "\n".join(original.content.splitlines()[passage.start_line - 1 : passage.end_line])
            ):
                raise AppError("index_incomplete", "Passage ranges failed original source validation.")
            if identity["provider"] != "disabled":
                vector = session.get(Embedding, passage.embedding_key) if passage.embedding_key else None
                if (
                    vector is None
                    or vector.config != identity
                    or vector.dimensions != identity["dimensions"]
                    or len(vector.vector) != identity["dimensions"]
                ):
                    raise AppError(
                        "index_incomplete", "Compatible vectors are missing from the staging index."
                    )
        snapshot.coverage = counters
    activate(job_id, token, snapshot_id)


def activate(job_id: str, token: int, snapshot_id: str):
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token)
        repo = session.scalar(select(Repository).where(Repository.id == job.repository_id).with_for_update())
        snapshot = session.get(Snapshot, snapshot_id)
        if snapshot.repository_id != repo.id:
            raise AppError("scope_mismatch", "Snapshot does not belong to the import repository.")
        if snapshot.state != "ready":
            snapshot.state = "ready"
            snapshot.ready_at = session.scalar(select(func.now()))
            session.flush([snapshot])
        activated = job.generation == repo.generation
        if activated:
            repo.active_snapshot_id = snapshot.id
        job.error = None
        job.status, job.stage = "succeeded", "activate"
        job.finished_at = session.scalar(select(func.now()))
        if job.attempt_started_at:
            job.execution_seconds += max(0, (job.finished_at - job.attempt_started_at).total_seconds())
            job.attempt_started_at = None
        job.lease_until = None
        job.result = {
            "snapshot_id": snapshot.id,
            "commit_sha": snapshot.commit_sha,
            "coverage": snapshot.coverage,
            "activated": activated,
            "reason": None if activated else "superseded",
        }
        emit(session, job, "succeeded", **job.result)


def validate_answer(output: dict, evidence: list[dict]) -> dict:
    from typing import Literal

    from pydantic import BaseModel, ConfigDict, Field, ValidationError

    class Segment(BaseModel):
        model_config = ConfigDict(extra="forbid")
        text: str = Field(min_length=1, max_length=5000)
        evidence_ids: list[str] = Field(min_length=1, max_length=12)

    class Output(BaseModel):
        model_config = ConfigDict(extra="forbid")
        outcome: Literal["answered", "partial", "insufficient_evidence"]
        segments: list[Segment] = Field(max_length=30)
        gaps: list[str] = Field(max_length=20)
        limitations: list[str] = Field(max_length=20)

    try:
        parsed = Output.model_validate(output)
    except ValidationError as exc:
        raise AppError(
            "invalid_model_output", "Answer did not match the required evidence format.", 503
        ) from exc
    known = {item["evidence_id"] for item in evidence}
    if any(set(segment.evidence_ids) - known for segment in parsed.segments):
        raise AppError(
            "invalid_model_output", "Answer cited evidence that was not selected for this run.", 503
        )
    if parsed.outcome in {"answered", "partial"} and not parsed.segments:
        raise AppError("invalid_model_output", "Answer outcome does not match its empty content.", 503)
    if parsed.outcome != "answered" and not parsed.gaps:
        raise AppError(
            "invalid_model_output", "Partial or unsupported answers must declare evidence gaps.", 503
        )
    return parsed.model_dump()


def answer_question(job_id: str, token: int, config, lease):
    checkpoint(job_id, token, "retrieve")
    with SessionLocal() as session:
        run = session.scalar(select(AnswerRun).where(AnswerRun.job_id == job_id))
        job = session.get(Job, job_id)
        snapshot = session.get(Snapshot, run.snapshot_id)
        repo = session.get(Repository, run.repository_id)
        if run.kind == "overview":
            rows = session.execute(
                select(Passage, SourceVersion)
                .join(SourceVersion)
                .join(SnapshotFile, SnapshotFile.source_version_id == SourceVersion.id)
                .where(SnapshotFile.snapshot_id == snapshot.id, Passage.config_hash == snapshot.config_hash)
                .order_by(
                    (SourceVersion.path == "README.md").desc(),
                    (SourceVersion.kind == "config").desc(),
                    SourceVersion.path,
                    Passage.start_line,
                )
                .limit(30)
            ).all()
            candidates = [
                {
                    "source_version_id": s.id,
                    "path": s.path,
                    "label": p.label,
                    "start_line": p.start_line,
                    "end_line": p.end_line,
                    "excerpt": p.excerpt,
                    "kind": s.kind,
                }
                for p, s in rows
            ]
            effective_mode = "overview_inventory"
        else:
            result = search(
                session,
                repo.id,
                run.question,
                snapshot.id,
                job.request.get("retrieval_mode", "hybrid"),
                limit=12,
                config=config,
            )
            candidates = result["results"]
            effective_mode = result["effective_mode"]
        evidence = []
        size = 0
        for candidate in candidates:
            item = {
                k: candidate[k]
                for k in ("source_version_id", "path", "label", "start_line", "end_line", "excerpt", "kind")
            }
            item["evidence_id"] = f"e{len(evidence) + 1}"
            added = len(str(item).encode())
            if size + added > 4800 or len(evidence) >= 12:
                continue
            size += added
            evidence.append(item)
        run_id, question, snapshot_id, sha, name, coverage = (
            run.id,
            run.question,
            snapshot.id,
            snapshot.commit_sha,
            repo.name,
            snapshot.coverage,
        )
    checkpoint(
        job_id,
        token,
        "assemble",
        evidence_count=len(evidence),
        effective_mode=effective_mode,
        paths=sorted({e["path"] for e in evidence}),
    )
    with SessionLocal.begin() as session:
        guard(session, job_id, token)
        run = session.get(AnswerRun, run_id)
        run.evidence = evidence
        session.execute(delete(RunEvidence).where(RunEvidence.run_id == run_id))
        for item in evidence:
            session.add(
                RunEvidence(
                    run_id=run_id,
                    repository_id=run.repository_id,
                    snapshot_id=run.snapshot_id,
                    evidence_id=item["evidence_id"],
                    source_version_id=item["source_version_id"],
                    path=item["path"],
                    start_line=item["start_line"],
                    end_line=item["end_line"],
                    excerpt=item["excerpt"],
                )
            )
        run.config = {
            "retrieval_mode": effective_mode,
            "provider": config.generation_provider,
            "model": config.generation_model,
            "temperature": 0.1,
        }
    if not evidence:
        output = {
            "outcome": "insufficient_evidence",
            "segments": [],
            "gaps": ["No relevant source evidence was retrieved for this question."],
            "limitations": [],
        }
    else:
        lease.check()
        if config.generation_provider != "groq" or not config.groq_api_key:
            raise AppError(
                "generation_disabled",
                "Configure a server-side Groq API key to generate answers. Source search is available.",
                503,
            )
        with SessionLocal.begin() as session:
            guard(session, job_id, token)
            session.execute(text("SELECT pg_advisory_xact_lock(781341002)"))
            used = session.scalar(
                select(func.coalesce(func.sum(UsageEvent.reserved_tokens), 0)).where(
                    UsageEvent.created_at >= func.date_trunc("day", func.now())
                )
            )
            reservation = 9200
            if used + reservation > config.daily_token_budget:
                raise AppError(
                    "daily_budget_exhausted", "Daily generation budget is disabled or exhausted.", 429
                )
            usage = UsageEvent(
                job_id=job_id, provider="groq", model=config.generation_model, reserved_tokens=reservation
            )
            session.add(usage)
            session.flush()
            usage_id = usage.id
        checkpoint(job_id, token, "generate")
        try:
            output, actual = generate(question, evidence, config)
        except Exception:
            with SessionLocal.begin() as session:
                session.get(UsageEvent, usage_id).outcome = "unknown"
            raise
        with SessionLocal.begin() as session:
            usage = session.get(UsageEvent, usage_id)
            usage.actual_tokens = actual
            usage.outcome = "settled" if actual is not None else "unknown"
            if actual is not None:
                usage.reserved_tokens = max(actual, 0)
    checkpoint(job_id, token, "validate")
    output = validate_answer(output, evidence)
    citations = [
        {**e, "source_url": source_url(name, sha, e["path"], e["start_line"], e["end_line"])}
        for e in evidence
    ]
    output.update(
        {
            "run_id": run_id,
            "kind": run.kind,
            "snapshot_id": snapshot_id,
            "commit_sha": sha,
            "citations": citations,
            "coverage": {**coverage, "inspected_files": len({e["path"] for e in evidence})},
        }
    )
    output["limitations"] = list(
        dict.fromkeys([*output["limitations"], "Static source inspection; repository code was not executed."])
    )
    lease.check()
    with SessionLocal.begin() as session:
        job = guard(session, job_id, token)
        # Re-validate persisted evidence membership and original ranges before publication.
        for item in evidence:
            membership = session.scalar(
                select(SnapshotFile).where(
                    SnapshotFile.snapshot_id == snapshot_id,
                    SnapshotFile.source_version_id == item["source_version_id"],
                    SnapshotFile.path == item["path"],
                    SnapshotFile.state == "included",
                )
            )
            source = session.get(SourceVersion, item["source_version_id"])
            if (
                not membership
                or source.repository_id != job.repository_id
                or "\n".join(source.content.splitlines()[item["start_line"] - 1 : item["end_line"]])
                != item["excerpt"]
            ):
                raise AppError("invalid_evidence", "Run evidence failed source/range validation.", 500)
        session.get(AnswerRun, run_id).output = output
        job.error = None
        job.status, job.stage = "succeeded", "publish"
        job.result = {"run_id": run_id}
        job.finished_at = session.scalar(select(func.now()))
        if job.attempt_started_at:
            job.execution_seconds += max(0, (job.finished_at - job.attempt_started_at).total_seconds())
            job.attempt_started_at = None
        job.lease_until = None
        emit(session, job, "succeeded", run_id=run_id)


def run_once(config=settings) -> bool:
    claimed = claim(config)
    if not claimed:
        return False
    job_id, token = claimed
    try:
        with Lease(job_id, token, config) as lease:
            with SessionLocal() as session:
                kind = session.get(Job, job_id).kind
            if kind == "import":
                import_repository(job_id, token, config, lease)
            else:
                answer_question(job_id, token, config, lease)
    except LostLease:
        logger.warning("Job %s lost its worker lease", job_id)
    except Exception as exc:
        if not isinstance(exc, (AppError, Cancelled)):
            # Log exception type/location without source/provider bodies or credentials.
            logger.error("Job %s failed with %s", job_id, type(exc).__name__)
        try:
            settle_error(job_id, token, exc, config)
        except LostLease:
            pass
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logger.info("Worker started; waiting for durable jobs")
    while not stop.is_set():
        try:
            worker_presence()
            worked = run_once()
        except Exception as exc:
            logger.error("Worker polling failed: %s", type(exc).__name__)
            worked = False
        if not worked:
            stop.wait(1)


if __name__ == "__main__":
    main()
