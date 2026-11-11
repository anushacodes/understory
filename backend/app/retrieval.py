import re
from urllib.parse import quote

from sqlalchemy import func, literal_column, select

from app.config import settings
from app.errors import AppError
from app.indexing import identifier_text
from app.jobs import ready_snapshot
from app.models import Embedding, Passage, Repository, SnapshotFile, SourceVersion
from app.providers import embed, embedding_identity


def source_url(name: str, sha: str, path: str, start: int, end: int) -> str | None:
    if name == "understory/fixture":
        return None
    return f"https://github.com/{name}/blob/{sha}/{quote(path, safe='/')}#L{start}-L{end}"


def search(
    session,
    repository_id: str,
    query: str,
    snapshot_id: str | None = None,
    mode: str = "lexical",
    kinds: list[str] | None = None,
    path_prefix: str = "",
    limit: int = 10,
    fallback: bool = False,
    config=settings,
) -> dict:
    snapshot = ready_snapshot(session, repository_id, snapshot_id)
    if mode not in {"exact", "lexical", "semantic", "hybrid"}:
        raise AppError("invalid_mode", "Search mode must be exact, lexical, semantic, or hybrid.")
    if not query.strip() or len(query) > 2000:
        raise AppError("invalid_query", "Enter a query between 1 and 2,000 characters.")
    if not 1 <= limit <= 20:
        raise AppError("invalid_limit", "Search result limit must be between 1 and 20.")
    if kinds and set(kinds) - {"code", "test", "doc", "config"}:
        raise AppError("invalid_kind", "Unsupported source kind.")
    if path_prefix.startswith("/") or ".." in path_prefix.split("/") or "\\" in path_prefix:
        raise AppError("invalid_path", "Use a repository-relative path prefix.")
    repo = session.get(Repository, repository_id)
    base = (
        select(Passage, SourceVersion)
        .join(SourceVersion, Passage.source_version_id == SourceVersion.id)
        .join(SnapshotFile, SnapshotFile.source_version_id == SourceVersion.id)
        .where(
            SnapshotFile.snapshot_id == snapshot.id,
            SnapshotFile.state == "included",
            SourceVersion.repository_id == repository_id,
            Passage.config_hash == snapshot.config_hash,
        )
    )
    if kinds:
        base = base.where(SourceVersion.kind.in_(kinds))
    if path_prefix:
        base = base.where(SourceVersion.path.startswith(path_prefix, autoescape=True))
    stable = (SourceVersion.path, Passage.start_line, Passage.id)
    lists = []
    requested_mode = mode
    warnings = []
    if mode == "exact":
        # Qualifiers are literal; SQL LIKE wildcard characters cannot expand the scope.
        terms = query.strip()
        matches = (
            base.where(
                (Passage.label == terms)
                | Passage.label.endswith("." + terms, autoescape=True)
                | Passage.label.startswith(terms, autoescape=True)
            )
            .order_by(*stable)
            .limit(50)
        )
        lists.append(list(session.execute(matches)))
    if mode in {"lexical", "hybrid"}:
        document = func.to_tsvector(literal_column("'simple'"), Passage.search_text)
        tsquery = func.plainto_tsquery(literal_column("'simple'"), identifier_text(query))
        ranked = (
            base.where(document.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(document, tsquery).desc(), *stable)
            .limit(50)
        )
        lexical = list(session.execute(ranked))
        # Concept questions often contain filler words. OR candidates remain ranked and scoped.
        if not lexical:
            tokens = re.findall(r"[A-Za-z0-9]+", identifier_text(query).lower())
            stop = {
                "where",
                "what",
                "which",
                "does",
                "this",
                "the",
                "are",
                "how",
                "is",
                "a",
                "an",
                "in",
                "to",
                "of",
                "and",
                "with",
                "for",
                "it",
                "explain",
                "repository",
                "project",
            }
            tokens = [t for t in tokens if t not in stop][:32]
            if tokens:
                broad = func.to_tsquery(literal_column("'simple'"), " | ".join(tokens))
                lexical = list(
                    session.execute(
                        base.where(document.op("@@")(broad))
                        .order_by(func.ts_rank_cd(document, broad).desc(), *stable)
                        .limit(50)
                    )
                )
        lists.append(lexical)
    if mode in {"semantic", "hybrid"}:
        try:
            identity = snapshot.config.get("embedding", {})
            if (
                identity.get("provider") != "fastembed"
                or config.embedding_provider != "fastembed"
                or identity.get("model") != config.embedding_model
            ):
                raise AppError(
                    "embedding_unavailable",
                    "This snapshot does not have a compatible local semantic index. Use lexical search or reimport with embeddings enabled.",
                    503,
                )
            if identity != embedding_identity(config):
                raise AppError(
                    "embedding_configuration_mismatch",
                    "The local model assets or preprocessing differ from this snapshot. Use lexical search or reimport with the current model.",
                    503,
                )
            vector = embed([query], config, query=True)[0]
            ranked = (
                base.join(Embedding, Embedding.key == Passage.embedding_key)
                .where(Embedding.dimensions == len(vector))
                .order_by(Embedding.vector.cosine_distance(vector), *stable)
                .limit(50)
            )
            lists.append(list(session.execute(ranked)))
        except AppError:
            if not fallback:
                raise
            mode = "lexical"
            warnings.append("Semantic retrieval unavailable; explicit lexical fallback was used.")
            if not lists:
                return search(
                    session,
                    repository_id,
                    query,
                    snapshot.id,
                    "lexical",
                    kinds,
                    path_prefix,
                    limit,
                    False,
                    config,
                ) | {"requested_mode": requested_mode, "warnings": warnings}
    fused = {}
    for hits in lists:
        for rank, (passage, source) in enumerate(hits, 1):
            key = passage.id
            if key not in fused:
                fused[key] = [passage, source, 0.0]
            fused[key][2] += 1 / (60 + rank)
    ordered = sorted(
        fused.values(), key=lambda item: (-item[2], item[1].path, item[0].start_line, item[0].id)
    )[:limit]
    hits = [
        {
            "evidence_id": passage.id,
            "source_version_id": source.id,
            "path": source.path,
            "kind": source.kind,
            "label": passage.label,
            "start_line": passage.start_line,
            "end_line": passage.end_line,
            "excerpt": passage.excerpt,
            "score": score,
            "source_url": source_url(
                repo.name, snapshot.commit_sha, source.path, passage.start_line, passage.end_line
            ),
        }
        for passage, source, score in ordered
    ]
    return {
        "snapshot_id": snapshot.id,
        "commit_sha": snapshot.commit_sha,
        "requested_mode": requested_mode,
        "effective_mode": mode,
        "coverage": snapshot.coverage,
        "warnings": warnings,
        "results": hits,
    }
