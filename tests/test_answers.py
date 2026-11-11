from dataclasses import replace

import pytest
from app.db import SessionLocal
from app.errors import AppError
from app.jobs import enqueue
from app.models import AnswerRun, Job, Repository, Snapshot, UsageEvent
from app.worker import run_once, validate_answer
from sqlalchemy import select


@pytest.fixture
def indexed(database, config):
    with SessionLocal.begin() as session:
        repo = Repository(name="understory/fixture")
        session.add(repo)
        session.flush()
        job, _ = enqueue(session, repo.id, "import", {"ref": "a"}, "fixture-a")
        repo_id = repo.id
    run_once(config)
    with SessionLocal() as session:
        snapshot_id = session.get(Repository, repo_id).active_snapshot_id
    return repo_id, snapshot_id


def queue_question(repo_id, key="question", snapshot_id=None):
    with SessionLocal.begin() as session:
        job, run = enqueue(
            session,
            repo_id,
            "question",
            {"question": "validate_payload", "snapshot_id": snapshot_id, "retrieval_mode": "lexical"},
            key,
        )
        return job.id, run.id


def test_answer_persists_exact_evidence_and_actual_usage(indexed, config, monkeypatch):
    repo_id, snapshot_id = indexed
    job_id, run_id = queue_question(repo_id)

    def fake_generate(question, evidence, config):
        return {
            "outcome": "answered",
            "segments": [
                {
                    "text": f"The inspected source includes {evidence[0]['path']}.",
                    "evidence_ids": [evidence[0]["evidence_id"]],
                }
            ],
            "gaps": [],
            "limitations": [],
        }, 200

    monkeypatch.setattr("app.worker.generate", fake_generate)
    run_once(
        replace(
            config, generation_provider="groq", groq_api_key="inert-test-credential", daily_token_budget=50000
        )
    )
    with SessionLocal() as session:
        run = session.get(AnswerRun, run_id)
        assert session.get(Job, job_id).status == "succeeded"
        assert run.output["snapshot_id"] == snapshot_id
        assert run.output["citations"]
        assert run.output["citations"][0]["excerpt"] == run.evidence[0]["excerpt"]
        usage = session.scalar(select(UsageEvent).where(UsageEvent.job_id == job_id))
        assert usage.actual_tokens == 200 and usage.outcome == "settled"


def test_unknown_citation_is_never_published(indexed, config, monkeypatch):
    repo_id, _ = indexed
    job_id, run_id = queue_question(repo_id)
    monkeypatch.setattr(
        "app.worker.generate",
        lambda *args: (
            {
                "outcome": "answered",
                "segments": [{"text": "Untrusted claim", "evidence_ids": ["invented-evidence"]}],
                "gaps": [],
                "limitations": [],
            },
            100,
        ),
    )
    run_once(
        replace(
            config, generation_provider="groq", groq_api_key="inert-test-credential", daily_token_budget=50000
        )
    )
    with SessionLocal() as session:
        assert session.get(Job, job_id).status == "failed"
        assert session.get(Job, job_id).error["code"] == "invalid_model_output"
        assert session.get(AnswerRun, run_id).output is None


def test_budget_exhaustion_prevents_provider_call(indexed, config, monkeypatch):
    repo_id, _ = indexed
    job_id, _ = queue_question(repo_id)

    def forbidden(*args):
        raise AssertionError("provider must not be called")

    monkeypatch.setattr("app.worker.generate", forbidden)
    run_once(
        replace(
            config, generation_provider="groq", groq_api_key="inert-test-credential", daily_token_budget=10
        )
    )
    with SessionLocal() as session:
        assert session.get(Job, job_id).error["code"] == "daily_budget_exhausted"
        assert session.scalar(select(UsageEvent).where(UsageEvent.job_id == job_id)) is None


def test_answer_stays_on_a_when_b_activates_during_generation(indexed, config, monkeypatch):
    repo_id, a_id = indexed
    job_id, run_id = queue_question(repo_id)

    def refresh_during_generation(question, evidence, provider):
        with SessionLocal.begin() as session:
            enqueue(session, repo_id, "import", {"ref": "b"}, "fixture-b")
        assert run_once(config)
        return {
            "outcome": "answered",
            "segments": [{"text": f"Source inspected: {evidence[0]['path']}.", "evidence_ids": ["e1"]}],
            "gaps": [],
            "limitations": [],
        }, 200

    monkeypatch.setattr("app.worker.generate", refresh_during_generation)
    run_once(
        replace(
            config, generation_provider="groq", groq_api_key="inert-test-credential", daily_token_budget=50000
        )
    )
    with SessionLocal() as session:
        run = session.get(AnswerRun, run_id)
        assert session.get(Job, job_id).status == "succeeded"
        assert session.get(Repository, repo_id).active_snapshot_id != a_id
        assert run.output["snapshot_id"] == a_id
        assert run.output["commit_sha"] == session.get(Snapshot, a_id).commit_sha


def test_idempotency_omitted_snapshot_replays_original_pin(indexed, config):
    repo_id, a_id = indexed
    job_id, run_id = queue_question(repo_id)
    with SessionLocal.begin() as session:
        repo = session.get(Repository, repo_id)
        alternate = Snapshot(
            repository_id=repo_id, commit_sha="b" * 40, config_hash="other", config={}, state="ready"
        )
        session.add(alternate)
        session.flush()
        repo.active_snapshot_id = alternate.id
    replay_job, replay_run = queue_question(repo_id)
    assert (replay_job, replay_run) == (job_id, run_id)
    with SessionLocal() as session:
        assert session.get(AnswerRun, run_id).snapshot_id == a_id


@pytest.mark.parametrize(
    "output",
    [
        {"outcome": "answered", "segments": [], "gaps": [], "limitations": []},
        {
            "outcome": "partial",
            "segments": [{"text": "claim", "evidence_ids": ["e1"]}],
            "gaps": [],
            "limitations": [],
        },
        {
            "outcome": "answered",
            "segments": [{"text": "claim", "evidence_ids": []}],
            "gaps": [],
            "limitations": [],
        },
    ],
)
def test_invalid_answer_shapes_are_rejected(output):
    with pytest.raises(AppError):
        validate_answer(output, [{"evidence_id": "e1"}])
