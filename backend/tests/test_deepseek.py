import httpx
import pytest

from app.config import Settings
from app.services.deepseek import (
    DeepSeekClient,
    DeepSeekUnavailableError,
)


def test_settings_load_model_and_hide_api_key(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=test-secret\n"
        "DEEPSEEK_BASE_URL=https://example.test/v1\n"
        "DEEPSEEK_MODEL=test-model\n"
        "DEEPSEEK_PROMPT_VERSION=v9\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_PROMPT_VERSION", raising=False)

    settings = Settings.from_env(env_file=env_file)

    assert settings.api_key == "test-secret"
    assert settings.base_url == "https://example.test/v1"
    assert settings.model == "test-model"
    assert settings.prompt_version == "v9"
    assert "test-secret" not in repr(settings)


def test_client_sends_authenticated_tool_request(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "unit-test-model")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test/v1")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_candidates",
                                        "arguments": '{"area":"学校体育馆"}',
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        )

    client = DeepSeekClient(
        Settings.from_env(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.complete(
        messages=[{"role": "user", "content": "找活动"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "search_candidates", "parameters": {}},
            }
        ],
    )

    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer unit-test-key"
    assert '"model":"unit-test-model"' in captured["body"].replace(" ", "")
    assert result.content is None
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls[0].call_id == "call-1"
    assert result.tool_calls[0].name == "search_candidates"
    assert result.tool_calls[0].arguments == '{"area":"学校体育馆"}'


def test_client_maps_non_success_response_to_safe_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "do-not-leak")
    monkeypatch.setenv("DEEPSEEK_MODEL", "unit-test-model")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad auth"}})

    client = DeepSeekClient(
        Settings.from_env(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(DeepSeekUnavailableError) as error:
        client.complete(messages=[{"role": "user", "content": "hi"}], tools=[])

    assert "do-not-leak" not in str(error.value)
    assert "401" in str(error.value)


def test_client_maps_timeout_to_unavailable(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "timeout-secret")
    monkeypatch.setenv("DEEPSEEK_MODEL", "unit-test-model")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = DeepSeekClient(
        Settings.from_env(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(DeepSeekUnavailableError) as error:
        client.complete(messages=[{"role": "user", "content": "hi"}], tools=[])

    assert "timeout-secret" not in str(error.value)
    assert str(error.value) == "DeepSeek request timed out"
