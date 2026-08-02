"""
Клиент GPTunnel API (OpenAI-совместимый).
Поддерживает streaming и переключение моделей.
"""

from __future__ import annotations

from typing import Generator

from openai import OpenAI

from config import GPTUNNEL_BASE_URL, AgentConfig
from secrets import SecretsService


class LLMClient:
    """Клиент для работы с GPTunnel API."""

    def __init__(self, config: AgentConfig):
        self._config = config
        self._client: OpenAI | None = None
        self._reconnect()

    def _reconnect(self):
        api_key = SecretsService.get_api_key()
        if api_key:
            self._client = OpenAI(
                api_key=api_key,
                base_url=GPTUNNEL_BASE_URL,
            )
        else:
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def set_api_key(self, key: str):
        SecretsService.set_api_key(key)
        self._reconnect()

    def set_model(self, model_id: str):
        self._config.model = model_id
        self._config.save()

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Синхронный запрос — возвращает полный ответ."""
        if not self._client:
            raise RuntimeError("API ключ не задан. Укажите ключ в настройках.")

        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=messages,
            temperature=temperature or self._config.temperature,
            max_tokens=max_tokens or self._config.max_tokens,
            extra_body={"useWalletBalance": self._config.use_wallet_balance},
        )
        return response.choices[0].message.content or ""

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Generator[str, None, None]:
        """Потоковый запрос — yield-ит токены по мере поступления."""
        if not self._client:
            raise RuntimeError("API ключ не задан. Укажите ключ в настройках.")

        stream = self._client.chat.completions.create(
            model=self._config.model,
            messages=messages,
            temperature=temperature or self._config.temperature,
            max_tokens=max_tokens or self._config.max_tokens,
            stream=True,
            extra_body={"useWalletBalance": self._config.use_wallet_balance},
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def list_models(self) -> list[dict]:
        """Получить список доступных моделей от GPTunnel."""
        if not self._client:
            return []
        try:
            models = self._client.models.list()
            result = []
            for m in models.data:
                provider = self._guess_provider(m.id)
                result.append({"id": m.id, "name": m.id, "provider": provider})
            return result
        except Exception:
            return []

    @staticmethod
    def _guess_provider(model_id: str) -> str:
        """Определить провайдера по ID модели."""
        mid = model_id.lower()
        if "gpt" in mid or "o1" in mid or "o3" in mid:
            return "OpenAI"
        if "claude" in mid:
            return "Anthropic"
        if "gemini" in mid:
            return "Google"
        if "mistral" in mid:
            return "Mistral"
        if "deepseek" in mid:
            return "DeepSeek"
        if "llama" in mid:
            return "Meta"
        if "qwen" in mid:
            return "Alibaba"
        return "GPTunnel"
