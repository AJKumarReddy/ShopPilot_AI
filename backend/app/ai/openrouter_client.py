"""The only module authorized to construct external AI HTTP requests."""

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.observability.telemetry import AI_ERRORS, AI_LATENCY

T = TypeVar("T", bound=BaseModel)
LOG = logging.getLogger(__name__)


class AIError(Exception):
    """Safe, provider-independent error; contains no upstream body or credentials."""

    def __init__(
        self,
        message: str = "ShopPilot is temporarily unable to process AI requests.",
        status: int = 503,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.status, self.retryable = status, retryable


class AIResponseError(AIError):
    pass


class EmbeddingMismatch(AIError):
    def __init__(self) -> None:
        super().__init__(
            "Embedding configuration differs from the index. Re-index the catalog.", 409, False
        )


@dataclass
class Usage:
    model: str
    operation: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage | None = None


class OpenRouterClient(Protocol):
    async def chat(
        self, messages: list[dict[str, Any]], *, reasoning: bool = False
    ) -> ChatResult: ...
    def chat_stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]: ...
    async def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ChatResult: ...
    async def structured_completion(self, messages: list[dict[str, Any]], schema: type[T]) -> T: ...
    async def embed_text(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    async def aclose(self) -> None: ...


class RealOpenRouterClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        usage_sink: Callable[[Usage], Awaitable[None]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.settings, self.usage_sink, self.sleep = settings, usage_sink, sleep
        self.http = httpx.AsyncClient(
            base_url=settings.openrouter_base_url + "/",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.openrouter_site_url,
                "X-Title": settings.openrouter_app_name,
            },
            timeout=httpx.Timeout(settings.openrouter_timeout),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
            follow_redirects=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def record_usage(
        self, data: dict[str, Any], operation: str, model: str, started: float
    ) -> Usage:
        tokens = data.get("usage") or {}
        usage = Usage(
            str(data.get("model") or model),
            operation,
            int(tokens.get("prompt_tokens") or tokens.get("total_tokens") or 0),
            int(tokens.get("completion_tokens") or 0),
            int((time.perf_counter() - started) * 1000),
        )
        AI_LATENCY.labels(operation, model).observe(usage.latency_ms / 1000)
        LOG.info("ai_request", extra={"safe_fields": usage.__dict__})
        if self.usage_sink:
            await self.usage_sink(usage)
        return usage

    async def request(
        self, endpoint: str, payload: dict[str, Any], fallback: bool = True
    ) -> tuple[dict[str, Any], Usage]:
        if not self.settings.openrouter_api_key.get_secret_value():
            raise AIError("OpenRouter is not configured.", retryable=False)
        models = [payload["model"]]
        if fallback:
            models += [
                m.strip() for m in self.settings.openrouter_fallback_models.split(",") if m.strip()
            ]
        last_error = AIError()
        for model in models:
            for attempt in range(self.settings.openrouter_retries + 1):
                started = time.perf_counter()
                delay = min(10.0, 0.4 * 2**attempt + random.uniform(0, 0.2))
                try:
                    response = await self.http.post(endpoint, json={**payload, "model": model})
                    if response.status_code >= 400 or response.is_redirect:
                        retryable = response.status_code == 429 or response.status_code >= 500
                        AI_ERRORS.labels(str(response.status_code)).inc()
                        if not retryable:
                            raise AIError(status=response.status_code, retryable=False)
                        try:
                            delay = min(
                                30.0, max(delay, float(response.headers.get("retry-after", 0)))
                            )
                        except ValueError:
                            pass
                        last_error = AIError(status=response.status_code)
                    else:
                        data = response.json()
                        if not isinstance(data, dict) or data.get("error"):
                            raise AIResponseError(retryable=False)
                        return data, await self.record_usage(data, endpoint, model, started)
                except (httpx.TimeoutException, httpx.TransportError):
                    AI_ERRORS.labels("transport").inc()
                    last_error = AIError()
                except (ValueError, TypeError) as exc:
                    raise AIResponseError(retryable=False) from exc
                if attempt < self.settings.openrouter_retries:
                    await self.sleep(delay)
        raise last_error

    @staticmethod
    def result(data: dict[str, Any], usage: Usage) -> ChatResult:
        try:
            message = data["choices"][0]["message"]
            return ChatResult(
                str(message.get("content") or ""), message.get("tool_calls") or [], usage
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise AIResponseError(retryable=False) from exc

    async def chat(self, messages: list[dict[str, Any]], *, reasoning: bool = False) -> ChatResult:
        model = (
            self.settings.openrouter_reasoning_model
            if reasoning
            else self.settings.openrouter_chat_model
        )
        data, usage = await self.request(
            "chat/completions", {"model": model, "messages": messages, "max_tokens": 800}
        )
        return self.result(data, usage)

    async def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ChatResult:
        data, usage = await self.request(
            "chat/completions",
            {
                "model": self.settings.openrouter_chat_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": 800,
            },
        )
        return self.result(data, usage)

    async def structured_completion(self, messages: list[dict[str, Any]], schema: type[T]) -> T:
        data, usage = await self.request(
            "chat/completions",
            {
                "model": self.settings.openrouter_chat_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": 1200,
            },
        )
        try:
            return schema.model_validate_json(self.result(data, usage).content)
        except ValidationError as exc:
            raise AIResponseError(
                "I couldn't reliably understand that request. Please rephrase it.", retryable=False
            ) from exc

    async def embed_text(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data, _ = await self.request(
            "embeddings",
            {
                "model": self.settings.openrouter_embedding_model,
                "input": texts,
                "dimensions": self.settings.embedding_dimensions,
            },
            fallback=False,
        )
        try:
            rows = sorted(data["data"], key=lambda x: x["index"])
            if [r["index"] for r in rows] != list(range(len(texts))):
                raise ValueError("Unexpected embedding indexes")
            vectors = [[float(n) for n in row["embedding"]] for row in rows]
            if any(len(v) != self.settings.embedding_dimensions for v in vectors):
                raise EmbeddingMismatch()
            import math

            if any(not math.isfinite(n) for v in vectors for n in v):
                raise ValueError("Non-finite embedding")
            return vectors
        except (ValueError, KeyError, TypeError) as exc:
            raise AIResponseError(retryable=False) from exc

    async def chat_stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        if not self.settings.openrouter_api_key.get_secret_value():
            raise AIError("OpenRouter is not configured.", retryable=False)
        model = self.settings.openrouter_chat_model
        # Once a token is emitted, do not retry and accidentally duplicate user-visible text.
        for attempt in range(self.settings.openrouter_retries + 1):
            emitted = False
            started = time.perf_counter()
            try:
                async with self.http.stream(
                    "POST",
                    "chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        "max_tokens": 800,
                    },
                ) as response:
                    if response.status_code != 200:
                        raise AIError(
                            status=response.status_code,
                            retryable=response.status_code == 429 or response.status_code >= 500,
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        if line[6:] == "[DONE]":
                            return
                        chunk = json.loads(line[6:])
                        if chunk.get("error"):
                            raise AIResponseError()
                        if chunk.get("usage"):
                            await self.record_usage(chunk, "chat/stream", model, started)
                        for choice in chunk.get("choices", []):
                            content = choice.get("delta", {}).get("content")
                            if content:
                                emitted = True
                                yield content
                    return
            except (httpx.HTTPError, AIError, ValueError) as exc:
                if (
                    emitted
                    or attempt == self.settings.openrouter_retries
                    or isinstance(exc, AIError)
                    and not exc.retryable
                ):
                    raise AIError() from exc
                await self.sleep(0.4 * 2**attempt + random.uniform(0, 0.2))
