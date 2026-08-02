"""
Конфигурация агента Шелдона Павса.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from paths import DATA_DIR, CONFIG_FILE, MEMORY_DIR, SKILLS_DIR, AGENTS_MD

# GPTunnel API
GPTUNNEL_BASE_URL = "https://gptunnel.ru/v1"

# Доступные модели
AVAILABLE_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI"},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "OpenAI"},
    {"id": "o1-preview", "name": "o1 Preview", "provider": "OpenAI"},
    {"id": "o3-mini", "name": "o3 Mini", "provider": "OpenAI"},
    {"id": "claude-3.7-sonnet", "name": "Claude 3.7 Sonnet", "provider": "Anthropic"},
    {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
    {"id": "claude-3.5-haiku", "name": "Claude 3.5 Haiku", "provider": "Anthropic"},
    {"id": "gemini-2.5-pro-exp", "name": "Gemini 2.5 Pro Exp", "provider": "Google"},
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google"},
    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "Google"},
    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "provider": "Google"},
    {"id": "mistral-large", "name": "Mistral Large", "provider": "Mistral"},
    {"id": "mistral-medium", "name": "Mistral Medium", "provider": "Mistral"},
    {"id": "mistral-small", "name": "Mistral Small", "provider": "Mistral"},
]

DEFAULT_MODEL = "gpt-4o"

# Палитра «Собачьей мудрости»
PALETTE = {
    "bg_main": "#1a1220",
    "bg_light": "#241c2e",
    "bg_whiter": "#f4eef6",
    "toolbar": "#2a1a3a",
    "toolbar_dark": "#342840",
    "accent": "#a078b8",
    "accent_dark": "#7a5a9e",
    "accent_darker": "#5c3d7a",
    "scrollbar": "#7a5a9e",
    "context_menu": "#f4eef6",
    "text_primary": "#e8dff0",
    "text_secondary": "#b8b0c0",
    "text_light": "#b0a0c0",
    "white": "#ffffff",
    "input_bg": "#1a1220",
    "user_bubble": "#2a1a3a",
    "assistant_bubble": "#342840",
    "border": "#4a3858",
    "success": "#6aab7e",
    "warning": "#c05050",
    "gold": "#d4a853",
}


_TRANSIENT_FIELDS = {"api_key"}


@dataclass
class AgentConfig:
    """Конфигурация агента, сохраняемая в JSON.

    api_key НЕ сохраняется в файл — он хранится в системном Credential Manager
    через SecretsService. Поле api_key существует только в runtime.
    """
    api_key: str = ""
    model: str = DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096
    active_skills: list[str] = field(default_factory=list)
    loaded_files: list[str] = field(default_factory=list)
    system_prompt_extra: str = ""
    use_wallet_balance: bool = True  # True = личный баланс, False = бизнес-аккаунт

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in self.__dict__.items() if k not in _TRANSIENT_FIELDS}
        CONFIG_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> "AgentConfig":
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                # Не загружаем api_key из файла — он в Credential Manager
                data.pop("api_key", None)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    @classmethod
    def get_model_name(cls, model_id: str) -> str:
        for m in AVAILABLE_MODELS:
            if m["id"] == model_id:
                return f"{m['name']} ({m['provider']})"
        return model_id
