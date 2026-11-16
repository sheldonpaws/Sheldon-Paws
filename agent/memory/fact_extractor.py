"""
Автоматическое извлечение фактов из диалога.
"""

from __future__ import annotations

import re

from .facts import FactsStore

_LABELS = {
    "age": "возраст",
    "occupation": "профессия / работа",
    "education": "образование / учёба",
    "interests": "интересы / хобби",
    "location": "город / место жительства",
    "family": "семья",
    "pets": "домашние животные",
    "personality": "черты характера",
}

# Паттерны: (регулярка, ключ факта, группа)
_PATTERNS: list[tuple[str, str, int]] = [
    (r"\bмне\s+(\d+)\s*(?:год|лет|года)", "age", 1),
    (r"\bмне\s+уже\s+(\d+)\s*(?:год|лет|года)", "age", 1),
    (r"\bя\s+работаю\s+(\w+(?:\s+\w+){0,4})", "occupation", 1),
    (r"\bя\s+(?:работаю|тружусь)\s+(?:как|в|на)\s+(\w+(?:\s+\w+){0,4})", "occupation", 1),
    (r"(?:^|,)\s*работаю\s+(?:как|в|на)?\s*(\w+(?:\s+\w+){0,4})", "occupation", 1),
    (r"\bмоя\s+профессия\s+[—‑–-]\s*(.+?)(?:\.|,|;|$)", "occupation", 1),
    (r"\bя\s+(\w+)\s+по\s+профессии", "occupation", 1),
    (r"\bя\s+(\w+(?:-\w+)?(?:\s+\w+){0,3})\s+(?:из|со|с|в|на)\s+профессии", "occupation", 1),
    (r"\bя\s+(?:учусь|учу|изучаю)\s+(.+?)(?:\.|,|;|$)", "education", 1),
    (r"\bучусь\s+(?:в|на)\s+(.+?)(?:\.|,|;|$)", "education", 1),
    (r"\bя\s+люблю\s+(.+?)(?:\.|,|;|$)", "interests", 1),
    (r"(?:^|,|;)\s*люблю\s+(.+?)(?:\.|,|;|$)", "interests", 1),
    (r"\bмне\s+нравится\s+(.+?)(?:\.|,|;|$)", "interests", 1),
    (r"\bобожаю\s+(.+?)(?:\.|,|;|$)", "interests", 1),
    (r"\bмоё\s+любимое\s+(?:занятие|хобби)\s+[—‑–-]\s*(.+?)(?:\.|,|;|$)", "interests", 1),
    (r"\bмои\s+увлечения\s+[—‑–-]\s*(.+?)(?:\.|,|;|$)", "interests", 1),
    (r"\bя\s+живу\s+(?:в|на)\s+(.+?)(?:\.|,|;|$)", "location", 1),
    (r"(?:^|,)\s*живу\s+(?:в|на)\s+(.+?)(?:\.|,|;|$)", "location", 1),
    (r"\bя\s+из\s+(.+?)(?:\.|,|;|$)", "location", 1),
    (r"\bмой\s+город\s+[—‑–-]\s*(.+?)(?:\.|,|;|$)", "location", 1),
    (r"\bу\s+меня\s+есть\s+(.+?)(?:\.|,|;|$)", "family", 1),
    (r"\bмой\s+(?:папа|мама|брат|сестра|муж|жена|сын|дочь)\s+(.+?)(?:\.|,|;|$)", "family", 1),
    (r"\bу\s+меня\s+(?:живёт|есть)\s+(?:собака|кот|кошка|пёс|питомец)\s+(.+?)(?:\.|,|;|$)", "pets", 1),
    (r"\bя\s+(?:очень|весьма|довольно)\s+(\w+)\s+(?:человек|парень|девушка)", "personality", 1),
]


def detect_facts(text: str, store: FactsStore) -> list[dict]:
    """Найти потенциальные факты в тексте без сохранения.
    
    Возвращает список словарей: {key, label, value}.
    Пропускает факты, которые уже есть в store.
    """
    results: list[dict] = []
    seen_keys: set[str] = set()
    for pattern, key, group in _PATTERNS:
        if key in seen_keys:
            continue
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(group).strip()
        if not value or len(value) > 200:
            continue
        # Пропустить, если такое значение уже сохранено
        existing = store.get_user_fact_all(key)
        if value.lower() in (v.lower() for v in existing):
            continue
        results.append({
            "key": key,
            "label": _LABELS.get(key, key),
            "value": value,
        })
        seen_keys.add(key)
    return results


def save_fact(key: str, value: str, store: FactsStore):
    """Сохранить подтверждённый факт."""
    store.set_user_fact(key, value)
