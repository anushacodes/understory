from app.providers import embedding_key


def test_cache_identity_includes_input_model_assets_and_preprocessing():
    identity = {
        "provider": "fastembed",
        "model": "small",
        "dimensions": 384,
        "asset_digest": "version-a",
        "preprocessing": "v1",
    }
    first = embedding_key("app/one.py\nvalidate\nsource", identity)
    assert first == embedding_key("app/one.py\nvalidate\nsource", identity)
    assert first != embedding_key("app/two.py\nvalidate\nsource", identity)
    for changed in [
        {"dimensions": 768},
        {"asset_digest": "version-b"},
        {"preprocessing": "v2"},
        {"model": "different"},
    ]:
        assert first != embedding_key("app/one.py\nvalidate\nsource", {**identity, **changed})


def test_refresh_reuses_compatible_vectors_and_rejects_changed_assets(database, config, monkeypatch):
    from dataclasses import replace

    import pytest
    from app.db import SessionLocal
    from app.errors import AppError
    from app.models import Embedding, Snapshot
    from app.retrieval import search
    from sqlalchemy import func, select
    from test_imports import add_repo, import_ref

    identity = {"provider": "fastembed", "model": "inert", "dimensions": 3, "asset_digest": "v1"}
    monkeypatch.setattr("app.worker.embedding_identity", lambda config: dict(identity))
    monkeypatch.setattr(
        "app.worker.embedding_input", lambda path, label, excerpt, config: path + label + excerpt
    )
    monkeypatch.setattr("app.worker.embed", lambda texts, config: [[1.0, 0.0, 0.0] for _ in texts])
    config = replace(config, embedding_provider="fastembed")
    repo_id = add_repo()
    a = import_ref(repo_id, "a", config)
    b = import_ref(repo_id, "b", config)
    with SessionLocal() as session:
        assert session.get(Snapshot, b).coverage["reused_embeddings"] > 10
        count = session.scalar(select(func.count()).select_from(Embedding))
    identity["asset_digest"] = "v2"
    c = import_ref(repo_id, "a", config, "changed-assets")
    assert c != a
    with SessionLocal() as session:
        assert session.get(Snapshot, c).coverage["reused_embeddings"] == 0
        assert session.scalar(select(func.count()).select_from(Embedding)) > count
        monkeypatch.setattr("app.retrieval.embedding_identity", lambda config: dict(identity))
        with pytest.raises(AppError):
            search(session, repo_id, "validation", a, "hybrid", config=config)
        result = search(
            session, repo_id, "validation", a, "hybrid", fallback=True, config=config
        )
        assert result["effective_mode"] == "lexical"
        assert result["warnings"]
