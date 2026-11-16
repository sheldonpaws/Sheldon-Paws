"""Тесты авто-создания навыков Sheldon-Paws.

Запуск (из корня проекта, без pytest):
    agent_env\\Scripts\\python.exe tests\\test_skills.py

Что проверяется:
- SkillStreamFilter прячет служебные блоки <skill>…</skill> из потока ответа;
- extract_skill_blocks / sanitize_name / write_skill — разбор и запись
  SKILL.md в домашнюю папку ~/.sheldon_paws/skills/;
- migrate_bundled_skills — перенос bundled-скиллов в домашнюю папку
  без затирания правок пользователя;
- discover_skills — пользовательские скиллы приоритетнее bundled, без дублей.

Все записи идут во временные папки: реальный ~/.sheldon_paws не трогается.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile

AGENT_DIR = pathlib.Path(__file__).resolve().parent.parent / "agent"
sys.path.insert(0, str(AGENT_DIR))

import skills.loader as loader_mod            # noqa: E402
import skills.skill_writer as writer_mod      # noqa: E402
from skills.loader import _extract_description, discover_skills  # noqa: E402
from skills.skill_writer import (            # noqa: E402
    SkillStreamFilter,
    extract_skill_blocks,
    migrate_bundled_skills,
    sanitize_name,
    write_skill,
)

fails: list[str] = []


def check(label: str, cond: bool, extra: object = "") -> None:
    print(("  OK   " if cond else "  FAIL ") + label + ("" if cond else f" — {extra}"))
    if not cond:
        fails.append(label)


# ── 1. Фильтр потока ────────────────────────────────────────────────

def run_stream(tokens: list[str]) -> tuple[str, str]:
    f = SkillStreamFilter()
    visible = "".join(f.feed(t) for t in tokens) + f.finish()
    return visible, f.raw


plain = "Обычный текст ответа."
vis, raw = run_stream([plain])
check("обычный текст проходит без потерь", vis == plain and raw == plain)

block = '<skill name="test-skill" description="Проверка">\nШаг 1.\nШаг 2.\n</skill>'
vis, raw = run_stream(["Начало. ", block, " Конец."])
check("блок скрыт, текст вокруг виден", vis == "Начало.  Конец.", repr(vis))
check("raw содержит блок", block in raw)

# худший случай: тег режется по токенам
tokens = ["Ответ.", "<sk", 'ill name="x" des', 'cription="О">', "тело", "</sk", "ill>", "Хвост."]
vis, raw = run_stream(tokens)
check("разрезанный по токенам блок скрыт", vis == "Ответ.Хвост.", repr(vis))
check("разрезанный блок добыт из raw", "тело" in raw and "</skill>" in raw)

two = ('<skill name="a" description="A">Тело A</skill> между '
       '<skill name="b" description="B">Тело B</skill> после')
vis, raw = run_stream([two])
check("два блока скрыты, между ними текст виден", vis == " между  после", repr(vis))

vis, raw = run_stream(["Текст </skill> ещё"])
check("лишний </skill> вычищается", vis == "Текст  ещё", repr(vis))

vis, raw = run_stream(["Ответ.", '<skill name="cut" description="X">', "обрыв"])
check("незакрытый блок скрыт до конца", vis == "Ответ.", repr(vis))
blocks = extract_skill_blocks(raw)
check("незакрытый блок всё равно разбирается",
      len(blocks) == 1 and blocks[0]["content"] == "обрыв", blocks)

# ── 2. Разбор блоков и санитизация имён ─────────────────────────────

b = extract_skill_blocks('а <skill name="My Skill" description="Описание">Тело</skill> б')
check("имя санитизировано", b[0]["name"] == "my-skill", b)
check("описание и тело на месте",
      b[0]["description"] == "Описание" and b[0]["content"] == "Тело")
check("пустое тело отбрасывается",
      extract_skill_blocks('<skill name="e" description="d">   </skill>') == [])
check("блок без name не роняет разбор",
      extract_skill_blocks('<skill description="d">Т</skill>')[0]["name"] == "skill")
check("санитизация: пути и точки", sanitize_name("../etc/passwd") == "etc-passwd",
      sanitize_name("../etc/passwd"))
check("санитизация: кириллица живёт", sanitize_name("Проверка навыка") == "проверка-навыка",
      sanitize_name("Проверка навыка"))
check("санитизация: пустое -> skill", sanitize_name("///") == "skill")

# ── 3. Запись скилла ────────────────────────────────────────────────

work = pathlib.Path(tempfile.mkdtemp(prefix="sheldon_skills_test_"))
tmp_user = work / "user_skills"

path = write_skill("My Skill", "Описание навыка", "Шаг 1.\nШаг 2.", base_dir=tmp_user)
check("файл создан по пути user/my-skill/SKILL.md",
      path == tmp_user / "my-skill" / "SKILL.md" and path.exists(), path)
text = path.read_text(encoding="utf-8")
check("формат SKILL.md", text.startswith("# my-skill\n\nОписание навыка\n\nШаг 1."), repr(text[:60]))

p2 = write_skill("z", "", "# Заголовок из тела\n\nТекст.", base_dir=tmp_user)
t2 = p2.read_text(encoding="utf-8")
check("заголовок тела стал описанием", "Заголовок из тела" in t2.split("\n\n")[1], repr(t2[:80]))
check("loader видит описание", _extract_description(text) == "Описание навыка",
      _extract_description(text))

write_skill("my-skill", "Новое описание", "Новое тело", base_dir=tmp_user)
check("существующий скилл обновляется",
      "Новое описание" in (tmp_user / "my-skill" / "SKILL.md").read_text(encoding="utf-8"))

# ── 4. Миграция bundled → домашняя папка ────────────────────────────

tmp_bundle = work / "bundle_skills"
for name in ["freelancer", "social_network_developer"]:
    d = tmp_bundle / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"# {name}\n\nОригинал из проекта.\n", encoding="utf-8")

copied = migrate_bundled_skills(user_dir=tmp_user, bundle_dir=tmp_bundle)
check("оба bundled перенесены в домашнюю папку",
      sorted(copied) == ["freelancer", "social_network_developer"], copied)

(tmp_user / "freelancer" / "SKILL.md").write_text(
    "# freelancer\n\nМОЯ ПРАВКА.\n", encoding="utf-8")
copied2 = migrate_bundled_skills(user_dir=tmp_user, bundle_dir=tmp_bundle)
check("повторная миграция ничего не трогает", copied2 == [], copied2)
check("правка пользователя сохранена",
      "МОЯ ПРАВКА" in (tmp_user / "freelancer" / "SKILL.md").read_text(encoding="utf-8"))

# ── 5. discover: пользовательские важнее bundled, без дублей ────────

loader_mod.USER_SKILLS_DIR = tmp_user
loader_mod.SKILLS_DIR = tmp_bundle
writer_mod.USER_SKILLS_DIR = tmp_user
writer_mod.SKILLS_DIR = tmp_bundle

names = [s.name for s in discover_skills()]
check("найдены все скиллы",
      sorted(names) == ["freelancer", "my-skill", "social_network_developer", "z"], names)
check("без дублей (bundled shadowed)", names.count("freelancer") == 1, names)
freel = next(s for s in discover_skills() if s.name == "freelancer")
check("показана домашняя (правленная) версия", "МОЯ ПРАВКА" in freel.content, freel.content[:60])

# ── 6. Сквозной сценарий: ответ модели → фильтр → запись → discover ─

answer = ("Готово, правило записал.\n"
          '<skill name="dog-walk" description="Как гулять с доберманом">\n'
          "1. Две прогулки в день.\n2. После дождя — вытереть лапы.\n"
          "</skill>")
f = SkillStreamFilter()
visible = "".join(f.feed(ch) for ch in answer) + f.finish()
check("в чат не попало ничего из блока",
      "<skill" not in visible and "dog-walk" not in visible, visible)
for blk in extract_skill_blocks(f.raw):
    write_skill(blk["name"], blk["description"], blk["content"], base_dir=tmp_user)
found = [s.name for s in discover_skills()]
check("навык дошёл до discover", "dog-walk" in found, found)
walk = next(s for s in discover_skills() if s.name == "dog-walk")
check("описание навыка в карточке", walk.description == "Как гулять с доберманом", walk.description)
check("тело навыка в содержимом", "После дождя — вытереть лапы" in walk.content)

shutil.rmtree(work, ignore_errors=True)
print()
print("ИТОГ:", "ВСЁ ЗЕЛЕНО" if not fails else f"ПРОВАЛЕНО: {fails}")
sys.exit(1 if fails else 0)
