"""
Сервис безопасного хранения секретов через Windows Credential Manager.

Использует keyring — кроссплатформенный доступ к системному хранилищу:
- Windows: Credential Manager (Control Panel → Credential Manager)
- macOS: Keychain
- Linux: Secret Service API / kwallet

Для супер-приложения — единая точка доступа ко всем секретам.
"""

from __future__ import annotations

import keyring

SERVICE_NAME = "SheldonPaws"
API_KEY_ENTRY = "gptunnel_api_key"


class SecretsService:
    """Единый сервис секретов для всех модулей приложения."""

    @staticmethod
    def get_api_key() -> str:
        """Получить API-ключ GPTunnel из системного хранилища."""
        return keyring.get_password(SERVICE_NAME, API_KEY_ENTRY) or ""

    @staticmethod
    def set_api_key(key: str):
        """Сохранить API-ключ GPTunnel в системное хранилище."""
        if key:
            keyring.set_password(SERVICE_NAME, API_KEY_ENTRY, key)
        else:
            SecretsService.delete_api_key()

    @staticmethod
    def delete_api_key():
        """Удалить API-ключ из системного хранилища."""
        try:
            keyring.delete_password(SERVICE_NAME, API_KEY_ENTRY)
        except keyring.errors.PasswordDeleteError:
            pass  # ключа и так нет — не ошибка
