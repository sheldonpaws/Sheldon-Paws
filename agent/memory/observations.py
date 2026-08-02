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

    def _load(self) -> list[dict]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return []

    def _save(self):
        self._file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, observation: str, context: str = ""):
        """Добавить новое наблюдение."""
        item = {
            "id": len(self._data),
            "text": observation,
            "context": context,
            "timestamp": datetime.now().isoformat(),
        }
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
        self._data = []
        self._save()