"""
История диалогов — хранится в JSON для быстрого поиска и навигации.
Имена файлов: ГГГГ-ММ-ДД_ЧЧ-ММ-СС##Название.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class DialogHistory:
    """Управление историей диалогов с Шелдоном."""

    def __init__(self, storage_dir: Path):
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._current_session: list[dict] = []
        self._current_session_id: str = ""       # timestamp
        self._current_title: str = ""
        self._meta: dict[str, dict] = self._load_meta()

    # ── Мета-данные сессий (модель и т.п.) ────────────────────

    def _meta_file(self) -> Path:
        return self._dir / "sessions_meta.json"

    def _load_meta(self) -> dict[str, dict]:
        path = self._meta_file()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_meta(self):
        self._meta_file().write_text(
            json.dumps(self._meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_session_model(self, session_id: str, model: str):
        self._meta.setdefault(session_id, {})["model"] = model
        self._save_meta()

    def get_session_model(self, session_id: str) -> str | None:
        entry = self._meta.get(session_id, {})
        return entry.get("model") if entry else None

    def remove_session_meta(self, session_id: str):
        self._meta.pop(session_id, None)
        self._save_meta()

    # ── Имена файлов ─────────────────────────────────────────

    @staticmethod
    def _make_filename(timestamp: str, title: str) -> str:
        if title:
            safe = title.replace("/", "-").replace("\\", "-").replace(":", "-")
            return f"{timestamp}##{safe}.json"
        return f"{timestamp}.json"

    @staticmethod
    def _parse_filename(stem: str) -> tuple[str, str]:
        """Вернуть (timestamp, title) из имени файла без расширения."""
        if "##" in stem:
            parts = stem.split("##", 1)
            return parts[0], parts[1]
        return stem, ""

    # ── Сессии ───────────────────────────────────────────────

    def new_session(self, title: str = "", model: str = "") -> str:
        """Начать новую сессию. Возвращает id (timestamp)."""
        self._save_current_session()
        now = datetime.now()
        self._current_session_id = now.strftime("%Y-%m-%d_%H-%M-%S_%f")
        self._current_title = title
        self._current_session = []
        if model:
            self.set_session_model(self._current_session_id, model)
        return self._current_session_id

    def rename_session(self, session_id: str, new_title: str):
        """Переименовать сессию по её id (timestamp)."""
        old_stem = self._make_filename(session_id, self._current_title).replace(".json", "")
        new_stem = self._make_filename(session_id, new_title).replace(".json", "")

        if old_stem == new_stem:
            self._current_title = new_title
            return

        old_path = self._dir / f"{old_stem}.json"
        new_path = self._dir / f"{new_stem}.json"
        if old_path.exists():
            old_path.rename(new_path)

        if session_id == self._current_session_id:
            self._current_title = new_title

    @property
    def current_title(self) -> str:
        return self._current_title

    # ── Сообщения ────────────────────────────────────────────

    def add_message(self, role: str, content: str):
        if not self._current_session_id:
            self.new_session()
        self._current_session.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_messages_for_api(self, max_messages: int = 50) -> list[dict]:
        messages = self._current_session[-max_messages:]
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def get_last_n(self, n: int = 10) -> list[dict]:
        return self._current_session[-n:]

    def search(self, query: str) -> list[dict]:
        query_lower = query.lower()
        return [
            m for m in self._current_session
            if query_lower in m["content"].lower()
        ]

    # ── Сохранение / загрузка ────────────────────────────────

    def _save_current_session(self):
        if not self._current_session_id:
            return
        filename = self._make_filename(self._current_session_id, self._current_title)
        filepath = self._dir / filename
        filepath.write_text(
            json.dumps(self._current_session, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save(self):
        self._save_current_session()

    def load_session(self, session_id: str) -> bool:
        """Загрузить сессию по id (timestamp). Находит файл по префиксу."""
        for f in self._dir.glob(f"{session_id}*.json"):
            if f.name == "sessions_meta.json":
                continue
            self._save_current_session()
            data = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
            self._current_session = data
            self._current_session_id = session_id
            _, self._current_title = self._parse_filename(f.stem)
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """Список всех сессий с названиями."""
        sessions = []
        for filepath in sorted(self._dir.glob("*.json"), reverse=True):
            if filepath.name == "sessions_meta.json":
                continue
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    continue
                ts, title = self._parse_filename(filepath.stem)
                first_user = next((m for m in data if m["role"] == "user"), None)
                sessions.append({
                    "id": ts,
                    "title": title or ts,
                    "messages": len(data),
                    "preview": (first_user["content"][:60] + "...") if first_user else "Пустая сессия",
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Удалить сессию с диска по её id."""
        for f in self._dir.glob(f"{session_id}*.json"):
            f.unlink()
            self.remove_session_meta(session_id)
            return True
        return False

    # ── Саммари сессий (короткий пересказ для контекстной вставки) ─────────────

    def save_session_summary(self, summary: str, timestamp: str = ""):
        """Сохранить саммари сессии в файл summary_<timestamp>.md"""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"summary_{timestamp}.md"
        filepath = self._dir / filename
        filepath.write_text(summary, encoding="utf-8")
        return filename

    def load_session_summary(self, timestamp: str) -> Optional[str]:
        """Прочитать саммари сессии по timestamp (без расширения)."""
        filename = f"summary_{timestamp}.md"
        filepath = self._dir / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def find_session_summary(self, session_id: str) -> Optional[str]:
        """Найти саммари сессии по её id (timestamp)."""
        if "##" in session_id:
            session_id = session_id.split("##", 1)[0]
        return self.load_session_summary(session_id)
