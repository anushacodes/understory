import json
from dataclasses import replace

import httpx
import pytest
from app.errors import AppError
from app.providers import generate

OriginalClient = httpx.Client


def transport(monkeypatch, handler):
    monkeypatch.setattr(
        "app.providers.httpx.Client",
        lambda **kwargs: OriginalClient(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_groq_json_contract_and_known_usage(config, monkeypatch):
    def response(request):
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-120b"
        assert body["reasoning_effort"] == "low"
        assert body["response_format"] == {"type": "json_object"}
        assert "tools" not in body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "outcome": "insufficient_evidence",
                                    "segments": [],
                                    "gaps": ["No source establishes this."],
                                    "limitations": [],
                                }
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 100},
            },
        )

    transport(monkeypatch, response)
    output, usage = generate(
        "question",
        [],
        replace(
            config,
            generation_provider="groq",
            groq_api_key="inert-test-credential",
            generation_model="openai/gpt-oss-120b",
        ),
    )
    assert output["outcome"] == "insufficient_evidence"
    assert usage == 100


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "provider_credentials", False),
        (403, "provider_credentials", False),
        (404, "model_unavailable", False),
        (429, "provider_unavailable", True),
        (503, "provider_unavailable", True),
    ],
)
def test_provider_failure_classification_and_retry_guidance(config, monkeypatch, status, code, retryable):
    transport(
        monkeypatch,
        lambda request: httpx.Response(
            status, headers={"Retry-After": "45"}, json={"error": {"message": "private provider detail"}}
        ),
    )
    with pytest.raises(AppError) as result:
        generate(
            "question", [], replace(config, generation_provider="groq", groq_api_key="inert-test-credential")
        )
    assert result.value.code == code
    assert result.value.retryable is retryable
    assert "private provider detail" not in result.value.message
    if retryable:
        assert result.value.retry_after == 45


def test_malformed_model_content_is_not_success(config, monkeypatch):
    transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "invalid output"}}]}),
    )
    with pytest.raises(AppError) as result:
        generate(
            "question", [], replace(config, generation_provider="groq", groq_api_key="inert-test-credential")
        )
    assert result.value.code == "invalid_model_output"
