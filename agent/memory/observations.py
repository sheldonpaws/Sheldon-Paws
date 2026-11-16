from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

class ObservationsStore:
    """Свободные наблюдения/заметки о диалогах с пользователем."""

    def __init__(self, storage_dir: Path):
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "observations.json"
        self._data: list[dict] = self._load()
        # Монотонный счётчик id: продолжаем от максимального существующего,
        # чтобы после clear() id не начинались заново с нуля.
        self._next_id = max(
            (item.get("id", -1) for item in self._data), default=-1
        ) + 1

    def _load(self) -> list[dict]:
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
        return []

    def _save(self):
        self._file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, observation: str, context: str = ""):
        """Добавить новое наблюдение. Возвращает его id."""
        item = {
            "id": self._next_id,
            "text": observation,
            "context": context,
            "timestamp": datetime.now().isoformat(),
        }
        self._next_id += 1
        self._data.append(item)
        self._save()
        return item["id"]

    def search(self, query: str) -> list[dict]:
        """Поиск по наблюдениям — простой keymatch."""
        query_lower = query.lower()
        results = []
        for item in self._data:
            if (query_lower in item["text"].lower() or
                    query_lower in (item.get("context", "") or "").lower()):
                results.append(item)
        return results

    def get_all(self) -> list[dict]:
        return list(self._data)

    def clear(self):
        """Очистить наблюдения (счётчик id при этом не сбрасывается)."""
        self._data = []
        self._save()
