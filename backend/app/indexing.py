import ast
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass
class Parsed:
    symbols: list[dict] = field(default_factory=list)
    passages: list[dict] = field(default_factory=list)
    error: str | None = None


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "__pycache__",
    ".tox",
    ".next",
    "site-packages",
    ".aws",
    ".ssh",
}
SECRET_NAMES = {
    "credentials",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "id_rsa",
    "id_ed25519",
    ".npmrc",
    ".pypirc",
    ".netrc",
}


def classify(path: str) -> tuple[str | None, str | None]:
    p = PurePosixPath(path)
    parts = p.parts
    name = p.name.lower()
    if any(part.lower() in EXCLUDED_DIRS for part in parts):
        return None, "excluded_directory"
    if (
        name.startswith(".env")
        or name in SECRET_NAMES
        or p.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
    ):
        return None, "secret_path"
    if name.endswith((".min.js", ".min.css", ".generated.py", "_pb2.py")):
        return None, "generated"
    if p.suffix == ".py":
        return (
            "test"
            if any(x in {"tests", "test"} for x in parts[:-1])
            or name.startswith("test_")
            or name.endswith("_test.py")
            else "code"
        ), None
    if p.suffix.lower() in {".md", ".rst"}:
        return "doc", None
    if p.suffix.lower() in {".toml", ".ini", ".cfg", ".json", ".yaml", ".yml"}:
        return "config", None
    return None, "unsupported_type"


def identifier_text(text: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text).replace("_", " ")


def parse(path: str, content: str, kind: str) -> Parsed:
    result = Parsed()
    lines = content.splitlines()
    if not lines:
        return result
    spans: list[tuple[int, int, str]] = []
    if kind in {"code", "test"}:
        try:
            tree = ast.parse(content, filename=path)
        except (SyntaxError, ValueError, RecursionError):
            result.error = "python_parse_error"
            return result
        module = path.removesuffix(".py").replace("/", ".")

        def walk(node, parents: list[str]):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start = min([child.lineno, *[d.lineno for d in child.decorator_list]])
                    qualified = ".".join([module, *parents, child.name])
                    result.symbols.append(
                        {
                            "name": child.name,
                            "qualified_name": qualified,
                            "kind": "class"
                            if isinstance(child, ast.ClassDef)
                            else "async_function"
                            if isinstance(child, ast.AsyncFunctionDef)
                            else "function",
                            "parent": ".".join([module, *parents]) if parents else None,
                            "start_line": start,
                            "end_line": child.end_lineno,
                        }
                    )
                    spans.append((start, child.end_lineno, qualified))
                    walk(child, [*parents, child.name])
                else:
                    walk(child, parents)

        try:
            walk(tree, [])
        except RecursionError:
            result.error = "python_parse_depth"
            return result
        # Imports, constants, module docstrings and module-level execution remain searchable.
        covered = {n for a, b, _ in spans for n in range(a, b + 1)}
        start = None
        for n in range(1, len(lines) + 2):
            if n <= len(lines) and n not in covered:
                if start is None:
                    start = n
            elif start is not None:
                spans.append((start, n - 1, module))
                start = None
    else:
        starts = [1]
        for n, line in enumerate(lines, 1):
            if n > 1 and (
                re.match(r"^#{1,6}\s", line)
                or re.match(r"^\[[^]]+\]", line)
                or (n < len(lines) and re.match(r"^[=~-]{3,}\s*$", lines[n]))
            ):
                starts.append(n)
        starts = sorted(set(starts))
        for i, start in enumerate(starts):
            end = starts[i + 1] - 1 if i + 1 < len(starts) else len(lines)
            spans.append((start, end, lines[start - 1].strip("# ")[:160] or path))
    for start, end, label in sorted(set(spans)):
        cursor = start
        while cursor <= end:
            # Conservative byte-bound chunks: UTF-8 bytes upper-bound byte-BPE tokens.
            # Local model tokenizer performs an additional exact limit check before embedding.
            stop = cursor
            size = len(f"{path}\n{label}\n".encode())
            while stop <= end and stop - cursor < 48:
                added = len(lines[stop - 1].encode()) + 1
                if stop > cursor and size + added > 1600:
                    break
                size += added
                stop += 1
            excerpt = "\n".join(lines[cursor - 1 : stop - 1])
            if excerpt.strip():
                result.passages.append(
                    {
                        "label": label,
                        "start_line": cursor,
                        "end_line": stop - 1,
                        "excerpt": excerpt,
                        "search_text": f"{path}\n{label}\n{identifier_text(label)}\n{excerpt}\n{identifier_text(excerpt)}",
                    }
                )
            cursor = stop
    return result


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
