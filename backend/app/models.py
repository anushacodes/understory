from datetime import UTC, datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class WorkerPresence(Base):
    __tablename__ = "worker_presence"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_scope: Mapped[str] = mapped_column(default="owner")
    name: Mapped[str] = mapped_column(String(201))
    provider_id: Mapped[str | None]
    default_ref: Mapped[str] = mapped_column(default="main")
    active_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("snapshots.id", use_alter=True, name="fk_active_snapshot")
    )
    generation: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("owner_scope", "name"),)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    commit_sha: Mapped[str] = mapped_column(String(40))
    config_hash: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default="staging")
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", "config_hash"),
        CheckConstraint("state IN ('staging','ready','failed')"),
    )


class SourceVersion(Base):
    __tablename__ = "source_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str]
    line_count: Mapped[int]
    byte_count: Mapped[int]
    __table_args__ = (UniqueConstraint("repository_id", "path", "content_hash"),)


class SnapshotFile(Base):
    __tablename__ = "snapshot_files"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_versions.id", ondelete="CASCADE")
    )
    byte_count: Mapped[int]
    state: Mapped[str]
    reason: Mapped[str | None]
    __table_args__ = (UniqueConstraint("snapshot_id", "path"),)


class Symbol(Base):
    __tablename__ = "symbols"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.id", ondelete="CASCADE"), index=True
    )
    parser: Mapped[str]
    name: Mapped[str] = mapped_column(index=True)
    qualified_name: Mapped[str] = mapped_column(index=True)
    kind: Mapped[str]
    parent: Mapped[str | None]
    start_line: Mapped[int]
    end_line: Mapped[int]
    __table_args__ = (UniqueConstraint("source_version_id", "parser", "qualified_name", "start_line"),)


class Passage(Base):
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.id", ondelete="CASCADE"), index=True
    )
    config_hash: Mapped[str]
    label: Mapped[str]
    start_line: Mapped[int]
    end_line: Mapped[int]
    excerpt: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    embedding_key: Mapped[str | None] = mapped_column(ForeignKey("embedding_cache.key"))
    __table_args__ = (
        UniqueConstraint("source_version_id", "config_hash", "start_line", "end_line", "label"),
    )


class Embedding(Base):
    __tablename__ = "embedding_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    config: Mapped[dict] = mapped_column(JSON)
    dimensions: Mapped[int]
    vector: Mapped[list[float]] = mapped_column(Vector())


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    owner_scope: Mapped[str] = mapped_column(default="owner")
    kind: Mapped[str]
    request: Mapped[dict] = mapped_column(JSON)
    request_hash: Mapped[str]
    idempotency_key: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued", index=True)
    stage: Mapped[str] = mapped_column(default="queued")
    generation: Mapped[int | None]
    resolved_sha: Mapped[str | None]
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("snapshots.id"))
    attempt: Mapped[int] = mapped_column(default=0)
    execution_seconds: Mapped[float] = mapped_column(Float, default=0)
    attempt_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[dict | None] = mapped_column(JSON)
    event_sequence: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("owner_scope", "repository_id", "kind", "idempotency_key"),
        CheckConstraint("status IN ('queued','running','retry_wait','succeeded','failed','cancelled')"),
        Index("ix_jobs_eligibility", "status", "retry_at", "lease_until"),
    )


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int]
    event: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("job_id", "sequence"),)


class AnswerRun(Base):
    __tablename__ = "answer_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    kind: Mapped[str]
    question: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    output: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str]
    model: Mapped[str]
    reserved_tokens: Mapped[int]
    actual_tokens: Mapped[int | None]
    outcome: Mapped[str] = mapped_column(default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RunEvidence(Base):
    __tablename__ = "run_evidence"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("answer_runs.id", ondelete="CASCADE"), index=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"))
    evidence_id: Mapped[str]
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"))
    path: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int]
    end_line: Mapped[int]
    excerpt: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("run_id", "evidence_id"),
        CheckConstraint("start_line >= 1 AND end_line >= start_line"),
    )
