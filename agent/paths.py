"""
Резолвинг путей для dev-режима и frozen exe (PyInstaller).

Три ключевых понятия:
- BUNDLE_DIR  — read-only контент (AGENTS.md, SKILL.md, статичные ресурсы)
                В dev: корень проекта. В frozen: sys._MEIPASS
- USER_DATA_DIR — writable данные пользователя (config, dialogs, facts, context, observations)
                  Всегда: ~/.sheldon_paws/
"""

from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


# ── Read-only bundled контент ──────────────────────────────

if _is_frozen():
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    # dev: корень проекта = parent agent/
    BUNDLE_DIR = Path(__file__).parent.parent

# ── Writable persistent данные пользователя ────────────────

USER_DATA_DIR = Path.home() / ".sheldon_paws"

# ── Производные пути ────────────────────────────────────────

ASSETS_DIR = BUNDLE_DIR / "assets"
AGENTS_MD = ASSETS_DIR / "Агент" / "AGENTS.md"
SKILLS_DIR = ASSETS_DIR / "Агент" / "skills"

DATA_DIR = USER_DATA_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
MEMORY_DIR = USER_DATA_DIR / "memory"
CONTEXT_DIR = USER_DATA_DIR / "context"
USER_SKILLS_DIR = USER_DATA_DIR / "skills"

# ── Пользовательские истории / файлы знаний ──────────────────
# Положи сюда .txt/.md — Шелдон прочитает их при запросе.
USER_STORIES_DIR = USER_DATA_DIR / "stories"
