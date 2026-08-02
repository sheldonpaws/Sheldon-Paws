"""
Загрузчик навыков — находит и парсит SKILL.md файлы.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from paths import SKILLS_DIR, USER_SKILLS_DIR


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
    skills: list[Skill] = []
    seen_names: set[str] = set()

    # Сначала загружаем пользовательские скиллы (имеют приоритет)
    if USER_SKILLS_DIR.exists():
        for skill_dir in sorted(USER_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8")
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
                content = skill_file.read_text(encoding="utf-8")
                description = _extract_description(content)
                skills.append(Skill(
                    name=skill_dir.name,
                    description=description,
                    content=content,
                    path=skill_file,
                ))

    return skills


def _extract_description(content: str) -> str:
    """Извлечь краткое описание из SKILL.md (первый параграф после заголовка)."""
    lines = content.strip().split("\n")
    for line in lines[1:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:120] + ("..." if len(stripped) > 120 else "")
    return "Навык без описания"
