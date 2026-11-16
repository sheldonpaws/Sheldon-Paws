# Шпаргалка по тестам

## Запуск

```bash
# Все тесты
pytest

# Один файл
pytest tests/test_config.py

# Один тест
pytest tests/test_config.py::test_save_load

# С подробным выводом
pytest -v

# С отладочным output (print в тестах)
pytest -s

# Только упавшие
pytest --tb=short
```

## Структура теста

```python
def test_название():
    # Arrange — подготовка
    config = AgentConfig(model="gpt-4o")

    # Act — действие
    config.model = "claude-3.5-sonnet"

    # Assert — проверка
    assert config.model == "claude-3.5-sonnet"
```

## Основные assert

```python
assert x == y              # равно
assert x != y              # не равно
assert x is None           # None
assert x is not None       # не None
assert "hello" in text     # подстрока в строке
assert len(items) == 3     # длина списка
assert Path(f).exists()    # файл существует
assert result is True      # bool
assertraises(Exception):   # ожидаем ошибку
```

## Fixtures (общие данные)

```python
# conftest.py — автоматически подхватывается pytest
import pytest

@pytest.fixture
def tmp_config(tmp_path):
    """Создаёт конфиг в временной папке."""
    from agent.config import AgentConfig
    # Подменяем пути чтобы не трогать реальные файлы.
    # ВАЖНО: config.py берёт DATA_DIR по значению (from paths import DATA_DIR),
    # поэтому подмена agent.paths на тест НЕ действует — правим поля config.
    # Плоский импорт: conftest должен добавить agent/ в sys.path.
    import config as cfg
    cfg.DATA_DIR = tmp_path / "data"
    cfg.CONFIG_FILE = cfg.DATA_DIR / "config.json"
    return AgentConfig()
```

## Мокинг (подмена зависимостей)

```python
from unittest.mock import patch, MagicMock

# Подменить HTTP-запрос
@patch("llm_client.openai.OpenAI")
def test_api_call(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    # Тестируем логику без реального API
```

## Тестирование исключений

```python
import pytest

def test_bad_file():
    with pytest.raises(ValueError, match="Файл не найден"):
        read_file("/nonexistent.txt")
```

## Параметризованные тесты

```python
@pytest.mark.parametrize("model", ["gpt-4o", "claude-3.5-sonnet", "gemini-2.0-flash"])
def test_models_available(model):
    assert model in [m["id"] for m in AVAILABLE_MODELS]
```

## Как тестировать SheldonPaws

### paths.py
```python
def test_bundle_dir_exists():
    assert BUNDLE_DIR.exists()

def test_agents_md_exists():
    assert AGENTS_MD.exists()

def test_skills_dir_has_skills():
    assert SKILLS_DIR.exists()
    skills = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]
    assert len(skills) >= 2
```

### config.py
```python
def test_config_save_load(tmp_path):
    # Подменяем пути (config берёт их по значению — правим сам config)
    import config as cfg
    cfg.DATA_DIR = tmp_path / "data"
    cfg.CONFIG_FILE = cfg.DATA_DIR / "config.json"

    config = AgentConfig(model="test-model")
    config.save()

    loaded = AgentConfig.load()
    assert loaded.model == "test-model"

def test_api_key_not_saved(tmp_path):
    # config берёт пути по значению — правим сам config
    import config as cfg
    cfg.DATA_DIR = tmp_path / "data"
    cfg.CONFIG_FILE = cfg.DATA_DIR / "config.json"

    config = AgentConfig(api_key="secret-123")
    config.save()

    raw = json.loads(cfg.CONFIG_FILE.read_text())
    assert "api_key" not in raw
```

### memory/
```python
def test_dialog_history_add_message(tmp_path):
    from memory.dialog_history import DialogHistory
    dh = DialogHistory(tmp_path / "dialogs")
    dh.add_message("user", "Привет")
    dh.add_message("assistant", "Привет!")

    messages = dh.get_messages_for_api()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"

def test_facts_store(tmp_path):
    from memory.facts import FactsStore
    fs = FactsStore(tmp_path / "facts")
    fs.set_user_fact("name", "Иван")

    assert fs.get_user_fact("name") == "Иван"
    assert fs.search("Иван") != []
```

### skills/
```python
def test_discover_skills():
    from skills.loader import discover_skills
    skills = discover_skills()
    assert len(skills) >= 2
    names = [s.name for s in skills]
    assert "freelancer" in names

def test_skill_has_content():
    from skills.loader import discover_skills
    skills = discover_skills()
    for s in skills:
        assert len(s.content) > 0
        assert s.description != "Навык без описания"
```

### system_prompt.py
```python
def test_build_system_prompt():
    from system_prompt import build_system_prompt
    config = AgentConfig(active_skills=[])
    prompt = build_system_prompt(config)
    assert "Шелдон Павс" in prompt
    assert "ФОРМАТ ОТВЕТА" in prompt
```

## Порядок действий

1. Установить: `pip install pytest`
2. Добавить в requirements.txt: `pytest`
3. Создать `tests/conftest.py` (общие fixtures)
4. Создать `tests/test_config.py`, `test_memory.py`, и т.д.
5. Запустить: `pytest -v`
6. Все зелёные? → собирать exe
