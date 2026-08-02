"""
Факты — структурированная память о пользователе и контексте.
Каждая категория в отдельном JSON-файле.
Значения хранятся списком — новые факты не перезаписывают старые.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


_CATEGORIES = ("user", "context", "preferences")


class FactsStore:
    """Хранилище фактов с накоплением значений."""

    def __init__(self, storage_dir: Path):
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, list[str]]] = {}
        self._migrate_old_format()
        self._load_all()

    def _migrate_old_format(self):
        """Конвертировать старый единый facts.json в user.json/context.json/preferences.json."""
        old = self._dir / "facts.json"
        if not old.exists():
            return
        try:
            raw = json.loads(old.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for cat in _CATEGORIES:
            if cat not in raw or not raw[cat]:
                continue
            cat_path = self._file_for(cat)
            if cat_path.exists():
                continue
            old_data = raw[cat]
            # Конвертировать скаляры в списки
            converted = {k: [v] if isinstance(v, str) else v for k, v in old_data.items()}
            cat_path.write_text(
                json.dumps(converted, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        # Переименовать старый файл, чтобы не мигрировать повторно
        old.rename(old.with_suffix(".bak"))

    def _file_for(self, category: str) -> Path:
        return self._dir / f"{category}.json"

    def _load_all(self):
        for cat in _CATEGORIES:
            path = self._file_for(cat)
            if path.exists():
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    # Поддержка старого формата (dict со скалярами)
                    if raw and isinstance(next(iter(raw.values())), str):
                        raw = {k: [v] for k, v in raw.items()}
                    self._data[cat] = raw
                except (json.JSONDecodeError, StopIteration):
                    self._data[cat] = {}
            else:
                self._data[cat] = {}

    def _save(self, category: str):
        path = self._file_for(category)
        path.write_text(
            json.dumps(self._data[category], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_all(self):
        for cat in _CATEGORIES:
            if cat in self._data:
                self._save(cat)

    # --- Накопление фактов ---

    def add_fact(self, category: str, key: str, value: str):
        """Добавить значение к существующему ключу или создать новый."""
        self._data.setdefault(category, {}).setdefault(key, []).append(value)
        self._save(category)

    def set_user_fact(self, key: str, value: str):
        self.add_fact("user", key, value)

    def set_context(self, key: str, value: str):
        self.add_fact("context", key, value)

    def set_preference(self, key: str, value: str):
        self.add_fact("preferences", key, value)

    # --- Чтение ---

    def get_user_fact(self, key: str) -> Optional[str]:
        """Вернуть последнее значение."""
        values = self._data.get("user", {}).get(key, [])
        return values[-1] if values else None

    def get_user_fact_all(self, key: str) -> list[str]:
        """Вернуть все сохранённые значения."""
        return list(self._data.get("user", {}).get(key, []))

    def get_all_user_facts(self) -> dict[str, str]:
        """Вернуть dict с последними значениями (для обратной совместимости)."""
        return {
            k: v[-1] for k, v in self._data.get("user", {}).items() if v
        }

    def get_all_context(self) -> dict[str, str]:
        return {
            k: v[-1] for k, v in self._data.get("context", {}).items() if v
        }

    def get_all_preferences(self) -> dict[str, str]:
        return {
            k: v[-1] for k, v in self._data.get("preferences", {}).items() if v
        }

    def get_context(self, key: str) -> Optional[str]:
        values = self._data.get("context", {}).get(key, [])
        return values[-1] if values else None

    def get_preference(self, key: str) -> Optional[str]:
        values = self._data.get("preferences", {}).get(key, [])
        return values[-1] if values else None

    # --- Поиск ---

    def search(self, query: str) -> list[dict]:
        """Поиск по всем фактам."""
        results = []
        query_lower = query.lower()
        for category in _CATEGORIES:
            for key, values in self._data.get(category, {}).items():
                for val in values:
                    if query_lower in key.lower() or query_lower in val.lower():
                        results.append({"category": category, "key": key, "value": val})
        return results

    # --- Экспорт ---

    def to_markdown(self) -> str:
        lines = ["# Память агента: факты\n"]
        for category in _CATEGORIES:
            items = self._data.get(category, {})
            if items:
                cat_title = {
                    "user": "О пользователе",
                    "context": "Контекст",
                    "preferences": "Предпочтения",
                }
                lines.append(f"\n## {cat_title.get(category, category)}\n")
                for key, values in items.items():
                    if len(values) == 1:
                        lines.append(f"- **{key}**: {values[0]}")
                    else:
                        lines.append(f"- **{key}**:")
                        for v in values:
                            lines.append(f"  - {v}")
        return "\n".join(lines)
