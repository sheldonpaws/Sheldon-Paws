"""
Загрузчик навыков — находит и парсит SKILL.md файлы.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from paths import SKILLS_DIR, USER_SKILLS_DIR
from .skill_writer import migrate_bundled_skills


@dataclass
class Skill:
    """Представление навыка агента."""
    name: str
    description: str
    content: str
    path: Path
    active: bool = False

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").replace("-", " ").title()


def discover_skills() -> list[Skill]:
    """Найти все доступные навыки в папке skills/."""
    # Домашняя папка скиллов должна существовать с первого старта:
    # у нового пользователя она создаётся здесь, а не ждёт первого скилла.
    try:
        USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[Навыки] Не удалось создать {USER_SKILLS_DIR}: {e}")

    # Однократный перенос bundled-скиллов в домашнюю папку (бандл удалён —
    # тогда миграция просто вернёт пустой список):
    # копия появляется только если её там ещё нет (правки не затираем).
    migrated = migrate_bundled_skills()
    if migrated:
        print(f"[Навыки] Перенесено в домашнюю папку: {', '.join(migrated)}")

    skills: list[Skill] = []
    seen_names: set[str] = set()

    # Сначала загружаем пользовательские скиллы (имеют приоритет)
    if USER_SKILLS_DIR.exists():
        for skill_dir in sorted(USER_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = _read_skill_file(skill_file, skill_dir.name)
                if content is None:
                    continue
                description = _extract_description(content)
                skills.append(Skill(
                    name=skill_dir.name,
                    description=description,
                    content=content,
                    path=skill_file,
                ))
                seen_names.add(skill_dir.name)

    # Затем загружаем bundled скиллы (пропускаем те, что уже есть в пользовательских)
    if SKILLS_DIR.exists():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name in seen_names:
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = _read_skill_file(skill_file, skill_dir.name)
                if content is None:
                    continue
                description = _extract_description(content)
                skills.append(Skill(
                    name=skill_dir.name,
                    description=description,
                    content=content,
                    path=skill_file,
                ))

    return skills


def _read_skill_file(skill_file: Path, skill_name: str) -> str | None:
    """Прочитать SKILL.md; при ошибке кодировки/чтения — предупредить и пропустить."""
    try:
        return skill_file.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"[Навыки] Пропущен навык «{skill_name}»: не удалось прочитать SKILL.md — {e}")
        return None


def _extract_description(content: str) -> str:
    """Извлечь краткое описание из SKILL.md (первый параграф после заголовка)."""
    lines = content.strip().split("\n")
    for line in lines[1:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:120] + ("..." if len(stripped) > 120 else "")
    return "Навык без описания"
