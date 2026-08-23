import httpx
import json

import pytest

from backend.provider import OpenAICompatibleProvider, ProviderError


def _success_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": "连接成功"}}]},
    )


def test_provider_retries_transient_http_status():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls == 1 else _success_response()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "test-key",
            "test-model",
            client=client,
            max_retries=1,
            retry_backoff_seconds=0,
        )
        assert provider.structured_chat("system", "user") == "连接成功"
    assert calls == 2


def test_provider_converts_timeout_to_clear_error_after_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "test-key",
            "test-model",
            client=client,
            max_retries=1,
            retry_backoff_seconds=0,
        )
        with pytest.raises(ProviderError, match="超时"):
            provider.structured_chat("system", "user")
    assert calls == 2


def test_provider_converts_network_error_to_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic network error", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "test-key",
            "test-model",
            client=client,
            max_retries=0,
        )
        with pytest.raises(ProviderError, match="网络连接失败"):
            provider.structured_chat("system", "user")


def test_provider_does_not_retry_authentication_error():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "test-key",
            "test-model",
            client=client,
            max_retries=1,
            retry_backoff_seconds=0,
        )
        with pytest.raises(ProviderError, match="HTTP 401"):
            provider.structured_chat("system", "user")
    assert calls == 1


def test_provider_probe_uses_a_short_but_usable_request():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return _success_response()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "synthetic-key",
            "synthetic-model",
            client=client,
            max_retries=0,
        )
        provider.probe()

    assert seen[0]["max_tokens"] == 16
    assert seen[0]["model"] == "synthetic-model"
    assert seen[0]["messages"][1]["content"] == "Reply with OK."


def test_provider_probe_accepts_empty_visible_content_from_reasoning_model():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "synthetic internal trace",
                        }
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "synthetic-key",
            "synthetic-model",
            client=client,
            max_retries=0,
        )
        provider.probe()


def test_structured_chat_still_rejects_empty_visible_content():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1",
            "synthetic-key",
            "synthetic-model",
            client=client,
            max_retries=0,
        )
        with pytest.raises(ProviderError, match="空内容"):
            provider.structured_chat("system", "user")
