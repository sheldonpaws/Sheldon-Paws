# 🐾 Sheldon-Paws — Шелдон Павс

**Шелдон Павс к вашим услугам.**

Десктопный чат-агент «Шелдон Павс» — полусобака-получеловек (доберман). Это Windows-приложение на PyQt6: общаешься с Шелдоном через локальный интерфейс, а он отвечает голосом своей личности через GPTunnel (OpenAI-совместимый API). Приложение ведёт память: диалоги, факты о пользователе, наблюдения и контекст.

---

## ✨ Возможности

- 💬 **Чат со стримингом** — ответы приходят по токенам в реальном времени
- 🧠 **Память Шелдона** — диалоги, факты, наблюдения, саммари сессий, контекст
- 💼 **Навыки (Skills)** — подключаемые роли (фрилансер, разработчик соцсети и др.)
- 🧩 **Загрузка файлов** — читает `.txt`/`.md`, подмешивает их в контекст
- 👤 **Профиль личности** — биография и характер живут в `assets/AGENTS.md`.
- 🔐 **Безопасное хранение ключа** — API-ключ лежит в Windows Credential Manager, а не в файлах конфигурации

---

## 🚀 Быстрый старт (разработка)

Требуется **Python 3.13**.

```bash
# Создать виртуальное окружение
python -m venv agent_env

# Установить зависимости
agent_env\Scripts\python.exe -m pip install -r requirements.txt

# Запустить приложение
agent_env\Scripts\python.exe main.py
```

При первом запуске нужно ввести API-ключ GPTunnel (кнопка «🔑 API» в тулбаре).

---

## 🔧 Сборка exe (PyInstaller)

Из корня проекта:

```powershell
agent_env\Scripts\python.exe -m PyInstaller `
  --noconfirm --clean `
  --onefile --windowed `
  --name SheldonPaws `
  --icon assets\doberman.ico `
  --paths agent `
  --add-data "assets;assets" `
  main.py
```

Готовый exe появится в `dist\SheldonPaws.exe`.

> `--add-data "assets;assets"` — кладёт `assets/` в `sys._MEIPASS/assets` (нужно `paths.py`); `--paths agent` — для плоских импортов. Спец-файл `SheldonPaws.spec` в репозитории есть — для повторяемости собирай через него. Данные пользователя всегда лежат во внешней папке `~/.sheldon_paws/` — при сборке/перемещении не теряются.

### Сборка onedir (папка с exe)

Если нужен не один файл, а папка (быстрый старт, все файлы на виду):

```bat
build_onedir.bat
```

Скрипт запускает `agent_env\Scripts\python.exe -m PyInstaller --noconfirm --clean SheldonPaws-onedir.spec`. Результат — папка `dist\SheldonPaws\` с `SheldonPaws.exe` и `_internal\` внутри. **Переносить и раздавать нужно папку целиком**: один exe без `_internal\` не запустится.

Спеки держи зеркальными: новый `.py` в `agent/` добавляй в `hiddenimports` обоих — `SheldonPaws.spec` (onefile) и `SheldonPaws-onedir.spec` (onedir).

---

## 📁 Структура проекта

```
main.py           # точка входа (корень проекта)
agent/            # код приложения (плоские импорты, без пакета agent)
  gui/            # PyQt6-интерфейс (окна, чат, диалоги)
  memory/         # память: диалоги, факты, наблюдения, контекст
  skills/         # загрузчик и реестр навыков
  tools/          # инструменты агента (чтение файлов и т.д.)
assets/           # персонаж, навыки, фотографии (read-only контент)
tests/            # план тестов (CHEATSHEET.md); самих тестов пока нет
agent_env/        # venv (не коммитится)
```

**Важные нюансы кода:**
- `agent/` использует **плоские импорты** (`from config import ...`), а не `agent.config`. `main.py` добавляет папку `agent/` в `sys.path`.
- Разделение данных: `assets/` — только чтение (в frozen — `sys._MEIPASS`), данные пользователя — всегда `~/.sheldon_paws/`.
- API-ключ хранится через `keyring` (Windows Credential Manager), `api_key` намеренно не сохраняется в `config.json`.

---

## ⚙️ Бэкенд

- **GPTunnel** — `https://gptunnel.ru/v1`, OpenAI-совместимый.
- Поддерживаются модели OpenAI, Anthropic, Google, Mistral и др. (список в `agent/config.py` в `AVAILABLE_MODELS`, либо тянется с сервера).
- Все LLM-запросы идут с `extra_body={"useWalletBalance": ...}` (личный/бизнес-баланс).

---

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE).

---

