from dataclasses import replace

import pytest
from app.connectors import GitHubConnector
from app.errors import AppError


def test_resolution_checks_provider_identity_and_pins_full_sha(config, monkeypatch):
    source = GitHubConnector(config)
    requests = []

    def request(path):
        requests.append(path)
        return (
            {"id": 42, "private": False, "full_name": "example/repository"}
            if len(requests) == 1
            else {"sha": "a" * 40}
        )

    monkeypatch.setattr(source, "request", request)
    assert source.resolve("example/repository", "feature/a") == "a" * 40
    assert source.provider_id == "42"
    assert requests == ["/repos/example/repository", "/repos/example/repository/commits/feature%2Fa"]


@pytest.mark.parametrize(
    "metadata",
    [
        {"id": 42, "private": True, "full_name": "example/repository"},
        {"id": 42, "private": False, "full_name": "other/repository"},
        {"id": None, "private": False, "full_name": "example/repository"},
    ],
)
def test_noncanonical_private_or_missing_identity_is_refused(config, monkeypatch, metadata):
    source = GitHubConnector(config)
    monkeypatch.setattr(source, "request", lambda path: metadata)
    with pytest.raises(AppError):
        source.identify("example/repository")


def test_import_request_budget_survives_attempt_recreation(database, config, monkeypatch):
    from app.db import SessionLocal
    from app.jobs import enqueue
    from app.models import Job
    from app.worker import run_once
    from test_imports import add_repo

    repo_id = add_repo()
    with SessionLocal.begin() as session:
        job, _ = enqueue(session, repo_id, "import", {"ref": "a"}, "spent-requests")
        job.checkpoint = {"github_requests": 20}
        job_id = job.id

    class RequestingSource:
        provider_id = None

        def resolve(self, *args):
            self.on_request()
            raise AssertionError("Network must not be reached")

    monkeypatch.setattr("app.worker.connector", lambda name, config: RequestingSource())
    run_once(replace(config))
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job.status == "failed"
        assert job.error["code"] == "github_budget"
        assert job.checkpoint["github_requests"] == 20
