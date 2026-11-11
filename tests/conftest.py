from dataclasses import replace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.config import settings
from app.db import SessionLocal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import close_all_sessions


@pytest.fixture
def database():
    """Every integration test gets an isolated schema in the real local PostgreSQL."""
    schema = "test_" + uuid4().hex
    admin = create_engine(settings.database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema},public"}
    ).execution_options(schema_translate_map={None: schema})
    migration_config = Config("alembic.ini")
    migration_config.attributes["version_table_schema"] = schema
    with engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "head")
    SessionLocal.configure(bind=engine)
    yield engine
    close_all_sessions()
    SessionLocal.configure(bind=admin)
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


@pytest.fixture
def config():
    return replace(
        settings,
        owner_token="test-owner-token",
        embedding_provider="disabled",
        generation_provider="disabled",
        groq_api_key="",
        daily_token_budget=0,
    )


@pytest.fixture
def client(database, config, monkeypatch):
    import app.main as api

    monkeypatch.setattr(api, "settings", config)
    with TestClient(api.app) as browser:
        browser.headers["Authorization"] = "Bearer test-owner-token"
        yield browser
