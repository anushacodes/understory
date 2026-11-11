import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

from app.errors import AppError
from app.indexing import classify


@dataclass
class File:
    path: str
    size: int
    kind: str | None
    content: str | None
    reason: str | None


def canonical_repository(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^https://github\.com/", "", value).removesuffix("/").removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", value) or value.split("/")[
        1
    ] in {".", ".."}:
        raise AppError("invalid_repository", "Use a public GitHub repository in owner/name format.")
    return value.lower()


def safe_archive(data: bytes, config) -> list[File]:
    if len(data) > config.max_archive_bytes:
        raise AppError("archive_size_limit", "Compressed archive exceeds its size budget.")
    files = []
    total = included = count = 0
    seen = set()
    try:
        archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
        with archive:
            root = None
            for member in archive:
                count += 1
                if count > config.max_entries:
                    raise AppError("archive_entry_limit", "Repository archive has too many entries.")
                raw = member.name
                parts = PurePosixPath(raw).parts
                if (
                    raw.startswith("/")
                    or "\\" in raw
                    or any(p in {"..", "."} for p in parts)
                    or not parts
                    or len(parts) > 21
                    or "\x00" in raw
                ):
                    raise AppError("unsafe_archive", "Repository archive contains an unsafe path.")
                if root is None:
                    root = parts[0]
                if parts[0] != root:
                    raise AppError("unsafe_archive", "Repository archive must have one root directory.")
                if member.isdir():
                    continue
                if not member.isfile() or len(parts) < 2:
                    raise AppError("unsafe_archive", "Links and special archive entries are unsupported.")
                path = "/".join(parts[1:])
                if path in seen:
                    raise AppError(
                        "unsafe_archive", "Repository archive contains duplicate normalized paths."
                    )
                seen.add(path)
                total += member.size
                if total > config.max_extracted_bytes:
                    raise AppError("archive_size_limit", "Repository extracted size exceeds its budget.")
                kind, reason = classify(path)
                if member.size > config.max_file_bytes:
                    kind, reason = None, "file_size_limit"
                content = None
                if kind:
                    source = archive.extractfile(member)
                    payload = source.read(config.max_file_bytes + 1)
                    if len(payload) != member.size:
                        raise AppError("invalid_archive", "Archive entry size does not match its metadata.")
                    try:
                        content = payload.decode("utf-8")
                        if "\x00" in content:
                            kind, reason, content = None, "binary", None
                    except UnicodeDecodeError:
                        kind, reason = None, "unsupported_encoding"
                    if content is not None:
                        included += len(payload)
                        if included > config.max_source_bytes:
                            raise AppError("source_size_limit", "Supported source exceeds the import budget.")
                files.append(File(path, member.size, kind, content, reason))
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise AppError("invalid_archive", "Repository archive could not be read.") from exc
    return files


class GitHubConnector:
    def __init__(self, config):
        self.config = config
        self.calls = 0

    def request(self, path: str, *, archive=False):
        self.calls += 1
        if self.calls > 20:
            raise AppError("github_budget", "GitHub request budget exhausted.")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Understory/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.config.github_token and not archive:
            headers["Authorization"] = f"Bearer {self.config.github_token}"
        base = "https://codeload.github.com" if archive else "https://api.github.com"
        try:
            with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", base + path, headers=headers) as response:
                    if response.status_code in {429, 500, 502, 503, 504} or (
                        response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0"
                    ):
                        raise AppError(
                            "github_unavailable",
                            "GitHub is rate-limited or temporarily unavailable.",
                            503,
                            True,
                        )
                    if response.status_code != 200:
                        raise AppError(
                            "github_rejected",
                            "GitHub rejected this repository/ref or returned an unsupported redirect.",
                        )
                    cap = self.config.max_archive_bytes if archive else 1024 * 1024
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > cap:
                            raise AppError(
                                "download_size_limit", "GitHub response exceeds the configured size limit."
                            )
                    return bytes(data) if archive else json.loads(data)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AppError(
                "github_unavailable", "GitHub request failed. The worker will retry when eligible.", 503, True
            ) from exc

    def resolve(self, name: str, ref: str) -> str:
        repo = self.request(f"/repos/{name}")
        if repo.get("private") or repo.get("full_name", "").lower() != name:
            raise AppError(
                "unsupported_repository", "Only the canonical public allowlisted repository can be imported."
            )
        commit = self.request(f"/repos/{name}/commits/{quote(ref, safe='')}")
        sha = commit.get("sha", "")
        if not re.fullmatch("[0-9a-f]{40}", sha):
            raise AppError("invalid_commit", "GitHub did not return a full commit SHA.")
        return sha

    def download(self, name: str, sha: str) -> bytes:
        if not re.fullmatch("[0-9a-f]{40}", sha):
            raise AppError("invalid_commit", "A full pinned SHA is required for archive retrieval.")
        return self.request(f"/{name}/tar.gz/{sha}", archive=True)


class FixtureConnector:
    """Inert synthetic corpus; never presented as a live GitHub repository."""

    root = Path(__file__).resolve().parents[2] / "fixtures"

    def __init__(self, config):
        self.config = config

    def sources(self, ref: str) -> dict[str, bytes]:
        directory = self.root / ("snapshot_b" if ref.lower() in {"b", "snapshot-b"} else "snapshot_a")
        return {
            str(p.relative_to(directory)): p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()
        }

    def resolve(self, name: str, ref: str) -> str:
        for candidate in ("a", "b"):
            files = self.sources(candidate)
            sha = hashlib.sha1(
                b"synthetic-understory\x00" + b"".join(k.encode() + b"\x00" + v for k, v in files.items())
            ).hexdigest()
            if (
                ref.lower() in {candidate, f"snapshot-{candidate}"}
                or ref == sha
                or (candidate == "a" and ref in {"main", "HEAD"})
            ):
                return sha
        raise AppError("invalid_ref", "Synthetic fixture refs are main, a, or b.")

    def download(self, name: str, sha: str) -> bytes:
        ref = next((r for r in ("a", "b") if self.resolve(name, r) == sha), None)
        if ref is None:
            raise AppError("invalid_commit", "Unknown synthetic fixture SHA.")
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for path, content in self.sources(ref).items():
                info = tarfile.TarInfo("fixture/" + path)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        return output.getvalue()


def connector(name: str, config):
    return FixtureConnector(config) if name == "understory/fixture" else GitHubConnector(config)
