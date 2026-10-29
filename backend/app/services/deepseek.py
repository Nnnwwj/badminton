from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


class DeepSeekUnavailableError(Exception):
    """Raised when the configured model service cannot return a usable reply."""


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ChatCompletion:
    content: str | None
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None


def _completion_from_payload(payload: dict[str, Any]) -> ChatCompletion:
    try:
        choice = payload["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError):
        raise DeepSeekUnavailableError(
            "DeepSeek returned an invalid response"
        ) from None

    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise DeepSeekUnavailableError("DeepSeek returned invalid content")

    tool_calls = []
    for item in message.get("tool_calls") or []:
        try:
            function = item["function"]
            call_id = item["id"]
            name = function["name"]
            arguments = function["arguments"]
        except (KeyError, TypeError):
            raise DeepSeekUnavailableError(
                "DeepSeek returned an invalid tool call"
            ) from None
        if not isinstance(arguments, str):
            raise DeepSeekUnavailableError(
                "DeepSeek returned invalid tool arguments"
            )
        tool_calls.append(
            ToolCall(call_id=str(call_id), name=str(name), arguments=arguments)
        )

    return ChatCompletion(
        content=content,
        tool_calls=tuple(tool_calls),
        finish_reason=choice.get("finish_reason"),
    )


class DeepSeekClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._http_client = http_client

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        client = self._http_client or httpx.Client(
            timeout=self.settings.timeout_seconds
        )
        close_client = self._http_client is None
        try:
            return client.post(
                f"{self.settings.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except httpx.TimeoutException:
            raise DeepSeekUnavailableError("DeepSeek request timed out") from None
        except httpx.HTTPError:
            raise DeepSeekUnavailableError("DeepSeek request failed") from None
        finally:
            if close_client:
                client.close()

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: dict[str, str] | None = None,
    ) -> ChatCompletion:
        body: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if response_format is not None:
            body["response_format"] = response_format

        response = self._post(body)
        if not response.is_success:
            raise DeepSeekUnavailableError(
                f"DeepSeek request failed with status {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError:
            raise DeepSeekUnavailableError(
                "DeepSeek returned invalid JSON"
            ) from None
        if not isinstance(payload, dict):
            raise DeepSeekUnavailableError("DeepSeek returned an invalid response")
        return _completion_from_payload(payload)
