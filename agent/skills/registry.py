"""
Реестр навыков — управление активными/неактивными навыками.
"""

from __future__ import annotations

from pathlib import Path

from .loader import Skill, discover_skills
from config import AgentConfig


class SkillRegistry:
    """Реестр навыков агента Шелдона."""

    def __init__(self, config: AgentConfig):
        self._config = config
        self._skills: list[Skill] = discover_skills()
        self._restore_active()

    def _restore_active(self):
        """Восстановить состояние активности из конфигурации."""
        for skill in self._skills:
            skill.active = skill.name in self._config.active_skills

    @property
    def all_skills(self) -> list[Skill]:
        return list(self._skills)

    @property
    def active_skills(self) -> list[Skill]:
        return [s for s in self._skills if s.active]

    def toggle_skill(self, skill_name: str) -> bool:
        """Переключить навык (активировать/деактивировать). Возвращает новое состояние."""
        for skill in self._skills:
            if skill.name == skill_name:
                skill.active = not skill.active
                self._sync_config()
                return skill.active
        return False

    def activate_skill(self, skill_name: str):
        for skill in self._skills:
            if skill.name == skill_name:
                skill.active = True
                break
        self._sync_config()

    def deactivate_skill(self, skill_name: str):
        for skill in self._skills:
            if skill.name == skill_name:
                skill.active = False
                break
        self._sync_config()

    def get_skill(self, skill_name: str) -> Skill | None:
        for skill in self._skills:
            if skill.name == skill_name:
                return skill
        return None

    def reload(self):
        """Перезагрузить навыки с диска."""
        self._skills = discover_skills()
        self._restore_active()

    def _sync_config(self):
        """Синхронизировать список активных навыков с конфигурацией."""
        self._config.active_skills = [s.name for s in self.active_skills]
        self._config.save()
