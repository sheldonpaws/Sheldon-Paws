"""
Клиент GPTunnel API (OpenAI-совместимый).
Поддерживает streaming и переключение моделей.
"""

from __future__ import annotations

from typing import Generator
from openai import OpenAI
from config import GPTUNNEL_BASE_URL, AgentConfig
from app_secrets import SecretsService

# Таймаут «лёгкого» сетевого запроса (список моделей), сек.
# Список моделей грузится в фоновом потоке, поэтому держать его долго незачем.
MODELS_TIMEOUT = 15.0


class LLMClient:
    """Клиент для работы с GPTunnel API."""

    def __init__(self, config: AgentConfig):
        self._config = config
        self._client: OpenAI | None = None
        self._api_key = ""
        # Модель, выбранная для текущего сеанса (не сохраняется в config).
        self._model_override: str | None = None
        self._reconnect()

    def _reconnect(self):
        api_key = SecretsService.get_api_key()
        self._api_key = api_key
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

    def set_api_key(self, key: str) -> bool:
        """Сохранить ключ и переподключиться. False — хранилище недоступно."""
        ok = SecretsService.set_api_key(key)
        self._reconnect()
        return ok

    @property
    def model(self) -> str:
        """Модель, реально используемая для запросов."""
        return self._model_override or self._config.model

    def set_model(self, model_id: str, *, persist: bool = False):
        """Выбрать модель.

        persist=True — сохранить её как глобальную (config.model);
        persist=False — использовать только в текущем сеансе,
        не меняя сохранённую в конфиге модель.
        """
        if persist:
            self._config.model = model_id
            self._model_override = None
            self._config.save()
        else:
            self._model_override = model_id

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
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self._config.temperature,
            max_tokens=max_tokens if max_tokens is not None else self._config.max_tokens,
            stream=True,
            extra_body={"useWalletBalance": self._config.use_wallet_balance},
        )
        for chunk in stream:
            if not chunk.choices:
                continue  # служебный чанк без вариантов ответа (например, idle)
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def list_models(self) -> list[dict]:
        """Получить список доступных моделей от GPTunnel.

        Запрос идёт с коротким таймаутом и без ретраев, чтобы не подвешивать
        ожидание (вызывается из фонового потока, но и там долгие таймауты ни к чему).
        """
        if not self._client:
            return []
        try:
            probe = OpenAI(
                api_key=self._api_key,
                base_url=GPTUNNEL_BASE_URL,
                timeout=MODELS_TIMEOUT,
                max_retries=0,
            )
            models = probe.models.list()
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
