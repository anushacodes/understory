import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql+psycopg://understory:understory@127.0.0.1:54329/understory"
        )
    )
    owner_token: str = field(default_factory=lambda: os.getenv("OWNER_TOKEN", ""))
    allowed_repositories: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            x.strip().lower()
            for x in os.getenv("ALLOWED_REPOSITORIES", "understory/fixture").split(",")
            if x.strip()
        )
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
        )
    )
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "disabled"))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    )
    model_cache: Path = field(default_factory=lambda: Path(os.getenv("MODEL_CACHE_DIR", ".cache/models")))
    generation_provider: str = field(default_factory=lambda: os.getenv("GENERATION_PROVIDER", "disabled"))
    generation_model: str = field(
        default_factory=lambda: os.getenv("GENERATION_MODEL", "llama-3.3-70b-versatile")
    )
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    daily_token_budget: int = field(default_factory=lambda: int(os.getenv("DAILY_TOKEN_BUDGET", "0")))
    lease_seconds: int = field(default_factory=lambda: int(os.getenv("JOB_LEASE_SECONDS", "60")))
    heartbeat_seconds: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_SECONDS", "15")))
    storage_limit: int = field(
        default_factory=lambda: int(os.getenv("STORAGE_LIMIT_BYTES", str(512 * 1024 * 1024)))
    )
    max_archive_bytes: int = 20 * 1024 * 1024
    max_extracted_bytes: int = 100 * 1024 * 1024
    max_file_bytes: int = 512 * 1024
    max_source_bytes: int = 20 * 1024 * 1024
    max_entries: int = 5000
    max_attempts: int = 3

    def indexing_config(self) -> dict:
        return {
            "parser": "python-ast-doc-lines-v1",
            "chunker": "structural-lines-v1",
            "classifier": "source-policy-v1",
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model if self.embedding_provider != "disabled" else None,
        }


settings = Settings()
