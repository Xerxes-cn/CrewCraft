"""OpenAI-compatible LLM provider wrapping AsyncOpenAI."""
from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
from openai import AsyncOpenAI


class OpenAICompatibleProvider:
    """Wraps AsyncOpenAI for any OpenAI-compatible API (DeepSeek, Qwen, Kimi, etc.)."""

    def __init__(self, api_key: str, base_url: str, default_model: str, timeout: float = 60.0):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
        )
        self.default_model = default_model

    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_completion_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_completion_raw(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ):
        """Return full message object (may contain .tool_calls)."""
        kwargs: dict = dict(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message

    async def chat_completion_stream_raw(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator:
        """Yield raw streaming chunks for tool-call detection."""
        kwargs = dict(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools
        stream = await self.client.chat.completions.create(**kwargs)
        async for chunk in stream:
            yield chunk
