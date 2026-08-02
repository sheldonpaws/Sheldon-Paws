"""
Инструмент: чтение загруженных файлов (txt, md).
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 МБ


class FileReaderTool(BaseTool):
    """Чтение текстовых файлов для контекста агента."""

    name = "file_reader"
    description = "Чтение содержимого текстовых файлов (txt, md) и добавление в контекст"

    def __init__(self):
        self._loaded_files: dict[str, str] = {}

    def read_file(self, filepath: str) -> ToolResult:
        """Прочитать файл и вернуть его содержимое."""
        path = Path(filepath)

        if not path.exists():
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

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="cp1251")
            except UnicodeDecodeError:
                return ToolResult(success=False, content="", error="Не удалось определить кодировку файла")

        self._loaded_files[path.name] = content
        return ToolResult(success=True, content=content)

    def remove_file(self, filename: str) -> bool:
        """Удалить файл из загруженных."""
        if filename in self._loaded_files:
            del self._loaded_files[filename]
            return True
        return False

    @property
    def loaded_files(self) -> dict[str, str]:
        return dict(self._loaded_files)

    @property
    def loaded_filenames(self) -> list[str]:
        return list(self._loaded_files.keys())

    def get_all_content(self) -> str:
        """Получить содержимое всех загруженных файлов для подстановки в промпт."""
        if not self._loaded_files:
            return ""
        parts = []
        for name, content in self._loaded_files.items():
            parts.append(f"### Файл: {name}\n\n{content}")
        return "\n\n".join(parts)

    def execute(self, **kwargs) -> ToolResult:
        filepath = kwargs.get("filepath", "")
        if not filepath:
            return ToolResult(success=False, content="", error="Не указан путь к файлу")
        return self.read_file(filepath)

    def clear(self):
        """Очистить все загруженные файлы."""
        self._loaded_files.clear()
