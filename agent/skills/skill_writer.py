"""
Авто-создание навыков: служебный блок <skill> в ответе модели.

Модель по инструкции из system_prompt кладёт в конец ответа блок

    <skill name="имя" description="Одно предложение">
    тело навыка (markdown)
    </skill>

Приложение:
- SkillStreamFilter — прячет блок от пользователя прямо в потоке токенов
  (в чат уходит только видимая часть, raw хранит полный ответ);
- extract_skill_blocks — разбирает блоки из полного текста;
- write_skill — сохраняет навык в домашнюю папку ~/.sheldon_paws/skills/<имя>/SKILL.md;
- migrate_bundled_skills — однократно переносит bundled-скиллы из проекта
  в домашнюю папку (правки пользователя не затираются).

Импорты плоские (соглашение проекта): модуль лежит в agent/skills/.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from paths import SKILLS_DIR, USER_SKILLS_DIR

START_TAG = "<skill"
END_TAG = "</skill>"

_ATTR_RE = re.compile(r'([a-zA-Z_]+)\s*=\s*"([^"]*)"')
_BLOCK_RE = re.compile(r"<skill\b([^>]*)>(.*?)(?:</skill>|\Z)", re.S | re.I)


def sanitize_name(name: str) -> str:
    """Имя каталога скилла: буквы/цифры/_/-, без путевых разделителей и точек."""
    name = (name or "").strip().lower()
    name = re.sub(r"[^0-9a-zа-яё_\-]+", "-", name, flags=re.IGNORECASE)
    name = name.strip("-_.")[:64]
    return name or "skill"


class SkillStreamFilter:
    """Фильтр потока токенов: скрывает блоки <skill>…</skill>.

    feed(token) -> видимая часть токена (возможно, пустая);
    raw        -> полный текст ответа, включая скрытые блоки;
    finish()   -> хвост, удержанный из-за возможного начала тега.
    """

    def __init__(self):
        self.raw = ""
        self._hidden = False
        self._buf = ""    # накопленное внутри незакрытого блока
        self._carry = ""  # хвост, который может оказаться началом <skill

    @property
    def hidden_open(self) -> bool:
        return self._hidden

    def feed(self, token: str) -> str:
        self.raw += token
        if self._hidden:
            self._buf += token
            return self._consume_end()
        data = self._carry + token
        self._carry = ""
        return self._consume_start(data)

    def finish(self) -> str:
        """Отдать удержанный хвост (последний шанс увидеть начало тега)."""
        out, self._carry = self._carry, ""
        return out

    def _consume_start(self, data: str) -> str:
        """Видимый режим: отдать текст до блока, лишние </skill> — выкинуть."""
        out = ""
        while True:
            s = data.find(START_TAG)
            e = data.find(END_TAG)
            if e != -1 and (s == -1 or e < s):
                out += data[:e]
                data = data[e + len(END_TAG):]
                continue
            if s == -1:
                keep = 0
                for k in range(1, len(START_TAG)):
                    if data.endswith(START_TAG[:k]):
                        keep = k
                        break
                if keep:
                    out += data[:-keep]
                    self._carry = data[-keep:]
                else:
                    out += data
                return out
            out += data[:s]
            data = data[s + len(START_TAG):]
            e = data.find(END_TAG)
            if e != -1:
                data = data[e + len(END_TAG):]
                continue
            self._hidden = True
            self._buf = data
            return out

    def _consume_end(self) -> str:
        """Скрытый режим: как только пришёл </skill> — вернуть хвост наружу."""
        e = self._buf.find(END_TAG)
        if e == -1:
            return ""
        tail = self._buf[e + len(END_TAG):]
        self._buf = ""
        self._hidden = False
        return self._consume_start(tail)


def extract_skill_blocks(raw: str) -> list[dict]:
    """Разобрать блоки <skill> из полного текста ответа.

    Незакрытый блок тоже считается (модель оборвала ответ) — тело берётся
    до конца текста. Возвращает [{"name", "description", "content"}, ...].
    """
    blocks: list[dict] = []
    for attrs, body in _BLOCK_RE.findall(raw or ""):
        a = dict(_ATTR_RE.findall(attrs))
        content = body.strip()
        if not content:
            continue
        blocks.append({
            "name": sanitize_name(a.get("name", "")),
            "description": (a.get("description") or "").strip(),
            "content": content,
        })
    return blocks


def write_skill(name: str, description: str, content: str,
                base_dir: Path | None = None) -> Path:
    """Сохранить навык: <base>/<имя>/SKILL.md (атомарная запись).

    Если тело начинается с заголовка «# …» — он снимается и идёт в описание,
    если описание пустое. Существующий скилл с тем же именем обновляется.
    """
    base = Path(base_dir) if base_dir is not None else USER_SKILLS_DIR
    safe = sanitize_name(name)

    body = (content or "").strip()
    first, sep, rest = body.partition("\n")
    if first.startswith("# "):
        if not description:
            description = first[2:].strip()
        body = rest.strip() if sep else ""

    desc = description or "Навык, сохранённый из диалога с Шелдоном."
    skill_dir = base / safe
    skill_dir.mkdir(parents=True, exist_ok=True)

    path = skill_dir / "SKILL.md"
    text = f"# {safe}\n\n{desc}\n\n{body}\n"
    tmp = skill_dir / "SKILL.md.tmp"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return path


def migrate_bundled_skills(user_dir: Path | None = None,
                           bundle_dir: Path | None = None) -> list[str]:
    """Перенести bundled-скиллы проекта в домашнюю папку пользователя.

    Копия создаётся только если в домашней папке такого скилла ещё нет —
    правки пользователя не затираются. Возвращает имена скопированных скиллов.
    """
    user = Path(user_dir) if user_dir is not None else USER_SKILLS_DIR
    bundle = Path(bundle_dir) if bundle_dir is not None else SKILLS_DIR
    copied: list[str] = []
    if not bundle.is_dir():
        return copied
    for entry in sorted(bundle.iterdir()):
        src = entry / "SKILL.md"
        if not entry.is_dir() or not src.is_file():
            continue
        dst = user / entry.name / "SKILL.md"
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied.append(entry.name)
    return copied
