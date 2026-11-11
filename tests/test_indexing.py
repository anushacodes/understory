from app.indexing import classify, parse


def test_decorated_async_nested_unicode_ranges():
    source = 'def tag(f):\n    return f\n\n@tag\nasync def café():\n    """Unicode café."""\n    def inner():\n        return "é"\n    return inner()\n'
    result = parse("pkg/example.py", source, "code")
    symbols = {s["qualified_name"]: s for s in result.symbols}
    outer = symbols["pkg.example.café"]
    assert outer["start_line"] == 4
    assert outer["end_line"] == 9
    assert symbols["pkg.example.café.inner"]["parent"] == "pkg.example.café"
    for passage in result.passages:
        assert passage["excerpt"] == "\n".join(
            source.splitlines()[passage["start_line"] - 1 : passage["end_line"]]
        )


def test_imports_and_module_constants_are_searchable():
    result = parse(
        "mod.py",
        '"""Module documentation."""\nimport json\nPORT = 8000\n\ndef start():\n    return PORT\n',
        "code",
    )
    assert any("import json" in p["excerpt"] for p in result.passages)
    assert any("PORT = 8000" in p["excerpt"] for p in result.passages)


def test_invalid_python_records_error_instead_of_execution():
    result = parse("broken.py", "def invalid(:\n  boom", "code")
    assert result.error == "python_parse_error"
    assert not result.passages


def test_markdown_and_rst_sections_preserve_lines():
    for path, source in [
        ("README.md", "# Heading\nintro\n\n## More\ncontent\n"),
        ("docs.rst", "Heading\n=======\nintro\n\nMore\n----\ncontent\n"),
    ]:
        result = parse(path, source, "doc")
        assert len(result.passages) >= 2
        for passage in result.passages:
            assert passage["excerpt"] == "\n".join(
                source.splitlines()[passage["start_line"] - 1 : passage["end_line"]]
            )


def test_source_policy_excludes_secrets_vendors_and_unsupported():
    assert classify(".env.production")[1] == "secret_path"
    assert classify("config/credentials.json")[1] == "secret_path"
    assert classify("vendor/danger.py")[1] == "excluded_directory"
    assert classify("web/client.ts")[1] == "unsupported_type"
    assert classify("tests/test_api.py")[0] == "test"
    assert classify("settings.yaml")[0] == "config"


def test_config_is_text_not_executable_yaml():
    payload = 'execute: !!python/object/apply:os.system ["touch /tmp/never-run"]'
    result = parse("settings.yaml", payload, "config")
    assert result.passages[0]["excerpt"] == payload
