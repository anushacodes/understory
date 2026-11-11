import io
import tarfile
from dataclasses import replace

import pytest
from app.connectors import canonical_repository, safe_archive
from app.errors import AppError


def archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, body, kind in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = len(body)
                tar.addfile(item, io.BytesIO(body))
            else:
                item.linkname = "/tmp/outside"
                tar.addfile(item)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "path,kind",
    [
        ("root/../../escape.py", tarfile.REGTYPE),
        ("/absolute.py", tarfile.REGTYPE),
        ("root/link.py", tarfile.SYMTYPE),
        ("root/hard.py", tarfile.LNKTYPE),
        ("root/device", tarfile.CHRTYPE),
    ],
)
def test_unsafe_entries_are_rejected(path, kind, config):
    with pytest.raises(AppError, match="unsafe|Links"):
        safe_archive(archive([(path, b"print('never executed')", kind)]), config)


def test_duplicate_normalized_path_is_rejected(config):
    with pytest.raises(AppError, match="duplicate"):
        safe_archive(
            archive([("root/a.py", b"x=1", tarfile.REGTYPE), ("root/a.py", b"x=2", tarfile.REGTYPE)]), config
        )


def test_excluded_binary_and_large_files_are_inventoried(config):
    files = safe_archive(
        archive(
            [
                ("root/a.py", b"x=1", tarfile.REGTYPE),
                ("root/b.py", b"a\x00b", tarfile.REGTYPE),
                ("root/.env", b"NOT_A_REAL_SECRET=example", tarfile.REGTYPE),
                ("root/web.js", b"const a=1", tarfile.REGTYPE),
            ]
        ),
        config,
    )
    assert files[0].content == "x=1"
    assert [f.reason for f in files[1:]] == ["binary", "secret_path", "unsupported_type"]
    limited = safe_archive(
        archive([("root/large.py", b"x" * 20, tarfile.REGTYPE)]), replace(config, max_file_bytes=10)
    )
    assert limited[0].reason == "file_size_limit"


def test_entry_and_decompression_budgets(config):
    payload = archive([("root/a.py", b"x" * 100, tarfile.REGTYPE), ("root/b.py", b"x", tarfile.REGTYPE)])
    for restricted in [
        replace(config, max_entries=1),
        replace(config, max_extracted_bytes=50),
        replace(config, max_source_bytes=50),
    ]:
        with pytest.raises(AppError):
            safe_archive(payload, restricted)


def test_tar_metadata_and_compressed_bytes_are_bounded(config):
    payload = archive([("root/a.py", b"x=1", tarfile.REGTYPE)])
    with pytest.raises(AppError):
        safe_archive(payload, replace(config, max_archive_bytes=1))
    with pytest.raises(AppError):
        safe_archive(payload, replace(config, max_extracted_bytes=1, max_entries=1))


@pytest.mark.parametrize(
    "name", ["https://evil.example/a/b", "../escape", "a/b/c", "a/..", "file:///tmp/source"]
)
def test_repository_input_cannot_select_arbitrary_hosts(name):
    with pytest.raises(AppError):
        canonical_repository(name)


def test_github_identity_normalization():
    assert canonical_repository("https://github.com/Owner/Project.git/") == "owner/project"
