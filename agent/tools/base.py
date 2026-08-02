"""
Базовый класс инструмента агента.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Результат выполнения инструмента."""
    success: bool
    content: str
    error: str = ""


class BaseTool(ABC):
    """Базовый класс для инструментов агента."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...

    @property
    def info(self) -> dict:
        return {"name": self.name, "description": self.description}
