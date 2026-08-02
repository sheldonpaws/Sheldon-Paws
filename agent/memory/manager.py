"""
Менеджер памяти — единый интерфейс ко всем типам памяти агента.
Координирует dialog_history, facts, observations и context.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from .dialog_history import DialogHistory
from .facts import FactsStore
from .observations import ObservationsStore
from .knowledge_base import KnowledgeBase
from paths import MEMORY_DIR, CONTEXT_DIR, ASSETS_DIR, USER_STORIES_DIR


class MemoryManager:
    """Менеджер памяти агента Шелдона."""

    def __init__(self, storage_dir: Path | None = None):
        self._dir = storage_dir or MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

        self.dialog = DialogHistory(self._dir / "dialogs")
        self.facts = FactsStore(self._dir / "facts")
        self.observations = ObservationsStore(self._dir / "observations")

        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        self._context_file = CONTEXT_DIR / "context.md"

        # База знаний из статических файлов
        self.knowledge = KnowledgeBase(ASSETS_DIR)
        USER_STORIES_DIR.mkdir(parents=True, exist_ok=True)
        self.user_stories = KnowledgeBase(USER_STORIES_DIR)

    # --- Контекст (Markdown) ---

    def get_context_md(self) -> str:
        """Прочитать текущий контекст в Markdown."""
        if self._context_file.exists():
            return self._context_file.read_text(encoding="utf-8")
        return ""

    def set_context_md(self, content: str):
        """Записать контекст в Markdown."""
        self._context_file.write_text(content, encoding="utf-8")

    def append_context_md(self, content: str):
        """Добавить к контексту."""
        existing = self.get_context_md()
        if existing:
            self.set_context_md(existing + "\n\n" + content)
        else:
            self.set_context_md(content)

    # --- Комбинированный доступ ---

    def get_full_context(self, user_query: str = "") -> str:
        """
        Получить полный контекст для подстановки в system prompt.
        Включает: факты + наблюдения + саммари сессий + context.md.
        Если передан user_query — факты и наблюдения фильтруются.
        """
        parts: list[str] = []

        # 1. Факты (релевантные запросу, если он есть, иначе все)
        if user_query:
            relevant_facts = self.facts.search(user_query)
            if relevant_facts:
                md_lines = ["# Память агента: факты"]
                for item in relevant_facts:
                    md_lines.append(f"- **{item['key']}**: {item['value']}")
                parts.append("\n".join(md_lines))
        facts_md = self.facts.to_markdown()
        if facts_md.strip() not in ("# Память агента: факты", ""):
            parts.append(facts_md)

        # 2. Наблюдения (фильтр по запросу, если он есть, иначе последние 10)
        if user_query:
            relevant_obs = self.observations.search(user_query)
            if relevant_obs:
                obs_lines = ["# Наблюдения", ""]
                for item in relevant_obs[:10]:
                    obs_lines.append(f"- {item['text']}")
                parts.append("\n".join(obs_lines))
        else:
            all_obs = self.observations.get_all()
            if all_obs:
                obs_lines = ["# Последние наблюдения", ""]
                for item in all_obs[-10:]:
                    obs_lines.append(f"- {item['text']}")
                parts.append("\n".join(obs_lines))

        # 3. Саммари сессий (последние 3)
        summaries = []
        for filepath in sorted(self.dialog._dir.glob("summary_*.md"), reverse=True)[:3]:
            content = filepath.read_text(encoding="utf-8")
            if content and len(content) > 50:
                summaries.append(content)
        if summaries:
            parts.append("## Последние саммари сессий")
            parts.extend(summaries)

        # 4. context.md
        context_md = self.get_context_md()
        if context_md:
            parts.append(context_md)

        # 5. Базовые знания Шелдона (assets/) — только по запросу
        if user_query:
            knowledge_chunks = self.knowledge.search(user_query)
            if knowledge_chunks:
                k_lines = ["# Мои базовые знания (файлы разработчика)", ""]
                for chunk in knowledge_chunks:
                    k_lines.append(f"### {chunk['file']}")
                    k_lines.append(chunk["text"])
                    k_lines.append("")
                parts.append("\n".join(k_lines))

        # 6. Пользовательские истории (~/.sheldon_paws/stories/) — только по запросу
        if user_query:
            story_chunks = self.user_stories.search(user_query)
            if story_chunks:
                s_lines = ["# Истории пользователя (мои файлы)", ""]
                for chunk in story_chunks:
                    s_lines.append(f"### {chunk['file']}")
                    s_lines.append(chunk["text"])
                    s_lines.append("")
                parts.append("\n".join(s_lines))

        return "\n\n".join(parts)

    # --- Экспорт/Импорт ---

    def export_session(self, filepath: Path):
        """Экспортировать текущую сессию, факты и наблюдения в файл."""
        data = {
            "dialog": self.dialog._current_session,
            "facts": self.facts._data,
            "observations": self.observations.get_all(),
            "context_md": self.get_context_md(),
        }
        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- Сохранение ---

    def save_all(self):
        """Сохранить все компоненты памяти."""
        self.dialog.save()
        # facts сохраняются автоматически при изменении

    def new_session(self, title: str = "", model: str = "") -> str:
        """Начать новую сессию диалога."""
        return self.dialog.new_session(title, model)
