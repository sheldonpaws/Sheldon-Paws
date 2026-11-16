"""
Инструмент: чтение загруженных файлов (txt, md).
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult
from paths import USER_DATA_DIR

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 МБ


class FileReaderTool(BaseTool):
    """Чтение текстовых файлов для контекста агента.

    Ключ словаря — абсолютный путь (resolve): файлы с одинаковыми именами
    из разных папок больше не конфликтуют.
    """

    name = "file_reader"
    description = "Чтение содержимого текстовых файлов (txt, md) и добавление в контекст"

    def __init__(self):
        self._loaded_files: dict[str, str] = {}
        # Белый список: корень ~/.sheldon_paws/ + файлы, явно выбранные
        # пользователем в диалоге (или сохранённые в конфиге после такого выбора).
        self._allowed_roots: set[Path] = {USER_DATA_DIR.expanduser().resolve()}
        self._allowed_files: set[str] = set()

    def _is_allowed(self, path: Path) -> bool:
        if str(path) in self._allowed_files:
            return True
        return any(root == path or root in path.parents for root in self._allowed_roots)

    def read_file(self, filepath: str, *, trusted: bool = False) -> ToolResult:
        """Прочитать файл и вернуть результат.

        trusted=True — файл явно выбран пользователем (диалог «Загрузить файл»
        или восстановление из конфига): он добавляется в белый список.
        """
        try:
            path = Path(filepath).expanduser().resolve()
        except OSError as e:
            return ToolResult(success=False, content="", error=f"Не удалось разобрать путь: {e}")

        if trusted:
            self._allowed_files.add(str(path))

        if not path.is_file():
            return ToolResult(success=False, content="", error=f"Файл не найден: {filepath}")

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return ToolResult(
                success=False, content="",
                error=f"Неподдерживаемый формат: {path.suffix}. Допустимы: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        if path.stat().st_size > MAX_FILE_SIZE:
            return ToolResult(
                success=False, content="",
                error=f"Файл слишком большой (макс. {MAX_FILE_SIZE // 1024 // 1024} МБ)"
            )

        if not self._is_allowed(path):
            return ToolResult(
                success=False, content="",
                error=f"Файл вне белого списка: {path}"
            )

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="cp1251")
            except UnicodeDecodeError:
                return ToolResult(success=False, content="", error="Не удалось определить кодировку файла")
        except OSError as e:
            return ToolResult(success=False, content="", error=f"Не удалось прочитать файл: {e}")

        self._loaded_files[str(path)] = content
        return ToolResult(success=True, content=content)

    @property
    def loaded_files(self) -> dict[str, str]:
        return dict(self._loaded_files)

    @property
    def loaded_filenames(self) -> list[str]:
        """Абсолютные пути загруженных файлов (для сохранения в конфиг)."""
        return list(self._loaded_files.keys())

    def get_all_content(self) -> str:
        """Получить содержимое всех загруженных файлов для подстановки в промпт."""
        if not self._loaded_files:
            return ""
        # Если два файла имеют одно имя — показываем полный путь, чтобы не путаться
        name_counts: dict[str, int] = {}
        for path_str in self._loaded_files:
            name = Path(path_str).name
            name_counts[name] = name_counts.get(name, 0) + 1
        parts = []
        for path_str, content in self._loaded_files.items():
            name = Path(path_str).name
            if name_counts[name] > 1:
                name = path_str
            parts.append(f"### Файл: {name}\n\n{content}")
        return "\n\n".join(parts)

    def execute(self, **kwargs) -> ToolResult:
        """Реализация абстрактного метода BaseTool (function-calling не подключён)."""
        filepath = kwargs.get("filepath", "")
        if not filepath:
            return ToolResult(success=False, content="", error="Не указан путь к файлу")
        return self.read_file(filepath, trusted=True)

    def clear(self):
        """Очистить все загруженные файлы."""
        self._loaded_files.clear()
