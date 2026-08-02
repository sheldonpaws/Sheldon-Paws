"""
Сборка системного промпта агента Шелдона Павса.
Динамически собирает: профиль личности + активные навыки + контекст из памяти.
"""

from __future__ import annotations

from config import AgentConfig
from paths import AGENTS_MD, SKILLS_DIR


def load_agents_md() -> str:
    """Загрузить основной профиль личности из AGENTS.md."""
    if AGENTS_MD.exists():
        return AGENTS_MD.read_text(encoding="utf-8")
    return "Ты — Шелдон Павс, полусобака-получеловек (доберман). Более подробный профиль недоступен."


def load_skill(skill_name: str) -> str:
    """Загрузить содержимое навыка из SKILL.md."""
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return ""


def build_system_prompt(
    config: AgentConfig,
    context_md: str = "",
    loaded_files_content: str = "",
) -> str:
    """
    Собрать полный системный промпт.

    Структура:
    1. Профиль личности (AGENTS.md)
    2. Активные навыки (SKILL.md)
    3. Контекст из памяти (context.md)
    4. Загруженные файлы
    5. Дополнительные инструкции
    """
    parts: list[str] = []

    # 1. Профиль личности
    profile = load_agents_md()
    parts.append(f"## ТВОЙ ПРОФИЛЬ ЛИЧНОСТИ\n\n{profile}")

    # 2. Активные навыки
    if config.active_skills:
        skills_text: list[str] = []
        for skill_name in config.active_skills:
            content = load_skill(skill_name)
            if content:
                skills_text.append(f"### Навык: {skill_name}\n\n{content}")
        if skills_text:
            parts.append("## ТВОИ АКТИВНЫЕ НАВЫКИ\n\n" + "\n\n".join(skills_text))

    # 3. Контекст из памяти
    if context_md:
        parts.append(f"## КОНТЕКСТ ИЗ ПАМЯТИ\n\n{context_md}")

    # 4. Загруженные файлы
    if loaded_files_content:
        parts.append(f"## ЗАГРУЖЕННЫЕ ФАЙЛЫ\n\n{loaded_files_content}")

    # 5. Дополнительные инструкции
    if config.system_prompt_extra:
        parts.append(f"## ДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ\n\n{config.system_prompt_extra}")

    # 6. Финальная инструкция — формат ответа
    parts.append(
        "## ФОРМАТ ОТВЕТА\n\n"
        "Отвечай в характере Шелдона Павса. "
        "Используй тёплый, спокойный тон с лёгкой иронией. "
        "Обращайся на «ты». "
        "Если знаешь имя пользователя — обращайся к нему по имени. "
        "Если уместно — используй метафоры из собачьего мира. "
        "Не упоминай, что ты ИИ, бот или программа. 🐾\n\n"
        "## ИСТОЧНИКИ ЗНАНИЙ\n\n"
        "В контексте могут быть два типа файлов:\n"
        "- **Мои базовые знания** — файлы разработчика о моей личности, бэкстори, профили.\n"
        "- **Истории пользователя** — файлы, которые пользователь сам положил в "
        "папку .sheldon_paws/stories/. Это его личные рассказы, заметки, знания.\n\n"
        "Если пользователь спрашивает про содержимое своей папки (stories) — "
        "отвечай на основе его файлов, а не моих базовых знаний."
    )

    return "\n\n---\n\n".join(parts)
