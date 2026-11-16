"""
Сервис безопасного хранения секретов через Windows Credential Manager.

Использует keyring — кроссплатформенный доступ к системному хранилищу:
- Windows: Credential Manager (Control Panel → Credential Manager)
- macOS: Keychain
- Linux: Secret Service API / kwallet

Для супер-приложения — единая точка доступа ко всем секретам.

ВАЖНО: файл называется app_secrets.py, а не secrets.py.
main.py добавляет agent/ в sys.path, и старое имя «secrets.py» затеняло
стандартный модуль secrets (из-за этого падал pydantic:
AttributeError: no attribute 'compare_digest').
"""

from __future__ import annotations

import keyring

SERVICE_NAME = "SheldonPaws"
API_KEY_ENTRY = "gptunnel_api_key"


class SecretsService:
    """Единый сервис секретов для всех модулей приложения.

    Все обращения к keyring защищены try/except: если хранилище недоступно
    (NoKeyringError / InitError и т.п.), методы возвращают безопасное
    значение вместо исключения — ошибка не должна ронять слоты PyQt.
    """

    @staticmethod
    def get_api_key() -> str:
        """Получить API-ключ GPTunnel из системного хранилища."""
        try:
            return keyring.get_password(SERVICE_NAME, API_KEY_ENTRY) or ""
        except Exception as e:  # noqa: BLE001 — любая ошибка хранилища не должна ронять приложение
            print(f"[Секреты] Не удалось прочитать API-ключ: {e}")
            return ""

    @staticmethod
    def set_api_key(key: str) -> bool:
        """Сохранить API-ключ. Пустой ключ удаляет его.

        Возвращает True при успехе и False при ошибке хранилища.
        """
        try:
            if key:
                keyring.set_password(SERVICE_NAME, API_KEY_ENTRY, key)
            else:
                SecretsService.delete_api_key()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[Секреты] Не удалось сохранить API-ключ: {e}")
            return False

    @staticmethod
    def delete_api_key() -> bool:
        """Удалить API-ключ. True — удалён или его и так не было."""
        try:
            keyring.delete_password(SERVICE_NAME, API_KEY_ENTRY)
            return True
        except keyring.errors.PasswordDeleteError:
            return True  # ключа и так нет — не ошибка
        except Exception as e:  # noqa: BLE001
            print(f"[Секреты] Не удалось удалить API-ключ: {e}")
            return False
