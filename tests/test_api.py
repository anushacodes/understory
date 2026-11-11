from app.db import SessionLocal
from app.models import Job, Repository
from app.worker import run_once
from sqlalchemy import select


def imported(client, config):
    response = client.post("/v1/repositories", json={"github_repository": "understory/fixture"})
    assert response.status_code == 201
    repo_id = response.json()["id"]
    response = client.post(
        f"/v1/repositories/{repo_id}/imports", json={"ref": "a"}, headers={"Idempotency-Key": "api-import"}
    )
    assert response.status_code == 202
    assert run_once(config)
    return repo_id, response.json()["job_id"]


def test_owner_authorization_and_resource_scope(client):
    client.headers.pop("Authorization")
    assert client.get("/v1/repositories").status_code == 401
    assert client.get("/v1/health").json() == {"status": "ok"}
    client.headers["Authorization"] = "Bearer test-owner-token"
    with SessionLocal.begin() as session:
        repo = Repository(name="hidden/source", owner_scope="another-owner")
        session.add(repo)
        session.flush()
        repo_id = repo.id
    assert client.get(f"/v1/repositories/{repo_id}").status_code == 404
    assert client.get(f"/v1/repositories/{repo_id}/tree").status_code == 404
    assert not client.get("/v1/repositories").json()["items"]


def test_source_search_filters_and_bounds(client, config):
    repo_id, _ = imported(client, config)
    result = client.get(
        f"/v1/repositories/{repo_id}/search", params={"query": "validate_payload", "mode": "exact"}
    )
    assert result.status_code == 200
    hit = next(hit for hit in result.json()["results"] if hit["path"] == "app/validation.py")
    source = client.get(
        f"/v1/repositories/{repo_id}/files",
        params={"path": hit["path"], "start_line": hit["start_line"], "end_line": hit["end_line"]},
    ).json()
    assert source["content"] == hit["excerpt"]
    assert source["commit_sha"] == result.json()["commit_sha"]
    assert (
        client.get(f"/v1/repositories/{repo_id}/files", params={"path": "vendor/ignored.py"}).status_code
        == 409
    )
    assert (
        client.get(f"/v1/repositories/{repo_id}/search", params={"query": "x", "limit": 1000}).status_code
        == 422
    )
    tests = client.get(
        f"/v1/repositories/{repo_id}/search",
        params={"query": "validation", "kinds": "test", "path_prefix": "tests/"},
    ).json()
    assert all(hit["kind"] == "test" and hit["path"].startswith("tests/") for hit in tests["results"])


def test_semantic_unavailable_and_explicit_fallback(client, config):
    repo_id, _ = imported(client, config)
    path = f"/v1/repositories/{repo_id}/search"
    assert client.get(path, params={"query": "validation", "mode": "hybrid"}).status_code == 503
    response = client.get(
        path, params={"query": "validation", "mode": "hybrid", "allow_lexical_fallback": True}
    )
    assert response.status_code == 200
    assert response.json()["requested_mode"] == "hybrid"
    assert response.json()["effective_mode"] == "lexical"
    assert response.json()["warnings"]


def test_durable_event_replay(client, config):
    repo_id, job_id = imported(client, config)
    response = client.get(f"/v1/jobs/{job_id}/events", headers={"Last-Event-ID": "1"})
    assert response.status_code == 200
    ids = [int(line.removeprefix("id: ")) for line in response.text.splitlines() if line.startswith("id: ")]
    assert ids and ids[0] == 2
    assert ids == sorted(set(ids))
    assert '"status": "succeeded"' in response.text


def test_cancel_queued_job_and_purge(client, config):
    repo_id, _ = imported(client, config)
    response = client.post(
        f"/v1/repositories/{repo_id}/imports", json={"ref": "b"}, headers={"Idempotency-Key": "queued-b"}
    )
    job_id = response.json()["job_id"]
    assert client.delete(f"/v1/repositories/{repo_id}").status_code == 409
    assert client.post(f"/v1/jobs/{job_id}/cancel").json()["status"] == "cancelled"
    assert client.delete(f"/v1/repositories/{repo_id}").status_code == 200
    with SessionLocal() as session:
        assert session.scalar(select(Job).where(Job.repository_id == repo_id)) is None


def test_invalid_inputs_are_structured(client):
    response = client.post("/v1/repositories", json={"github_repository": "https://evil.example/a/b"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_repository"
    assert response.headers["x-request-id"]
    response = client.post("/v1/repositories", json={"github_repository": "a/b", "unexpected": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_chunked_request_size_is_bounded(client):
    def chunks():
        yield b'{"github_repository":"'
        yield b"x" * 20000
        yield b'"}'

    response = client.post("/v1/repositories", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
