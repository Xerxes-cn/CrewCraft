"""LLM Manager — unified entry point for all LLM calls."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from crewai.llms.providers.openai.completion import OpenAICompletion

from app.config import settings
from app.llm.provider import OpenAICompatibleProvider

PRESETS = {
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
}


def build_crewai_llm(llm_config: dict | None = None) -> OpenAICompletion:
    """Build a CrewAI-compatible LLM from global settings merged with per-agent overrides."""
    config = llm_config or {}
    preset = PRESETS.get(settings.llm_provider, {})
    api_key = settings.llm_api_key or settings.deepseek_api_key
    base_url = settings.llm_base_url or preset.get("base_url", settings.deepseek_base_url)
    model = settings.llm_model or preset.get("model", settings.deepseek_model)

    return OpenAICompletion(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
    )


class LLMManager:
    _provider: OpenAICompatibleProvider | None = None

    def configure(self, api_key: str, base_url: str, model: str) -> None:
        self._provider = OpenAICompatibleProvider(api_key, base_url, model)

    def _ensure_provider(self) -> OpenAICompatibleProvider:
        if self._provider is None:
            self._init_from_settings()
        assert self._provider is not None
        return self._provider

    def _init_from_settings(self) -> None:
        preset = PRESETS.get(settings.llm_provider, {})
        # New unified config takes precedence, fall back to legacy deepseek_ config
        api_key = settings.llm_api_key or settings.deepseek_api_key
        base_url = settings.llm_base_url or preset.get("base_url", settings.deepseek_base_url)
        model = settings.llm_model or preset.get("model", settings.deepseek_model)
        self.configure(api_key, base_url, model)

    # ---- Delegating methods ----

    async def chat_completion(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096,
    ) -> str:
        return await self._ensure_provider().chat_completion(messages, model, temperature, max_tokens)

    async def chat_completion_stream(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._ensure_provider().chat_completion_stream(messages, model, temperature, max_tokens):
            yield chunk

    async def chat_completion_raw(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ):
        return await self._ensure_provider().chat_completion_raw(messages, model, temperature, max_tokens, tools)

    async def chat_completion_stream_raw(
        self, messages: list[dict], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator:
        async for chunk in self._ensure_provider().chat_completion_stream_raw(messages, model, temperature, max_tokens, tools):
            yield chunk


llm = LLMManager()
