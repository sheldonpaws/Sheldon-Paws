from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QComboBox, QHBoxLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from config import PALETTE
from gui.styles import app_stylesheet


_CATEGORIES = [
    ("about", "ℹ️ Обо мне"),
    ("interests", "🎯 Интересы / хобби"),
    ("occupation", "💼 Работа / профессия"),
    ("location", "📍 Город / место"),
    ("family", "👨‍👩‍👧‍👦 Семья"),
    ("pets", "🐾 Домашние животные"),
    ("education", "📚 Образование"),
    ("preference", "⭐ Предпочтения"),
    ("other", "📝 Другое"),
]


class RememberDialog(QDialog):
    """Диалог сохранения выделенного текста в память."""

    def __init__(self, role: str, selected_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Шелдон Павс — запомнить 🧠")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        who = "Ты" if role == "user" else "Шелдон"
        layout.addWidget(QLabel(f"Выделено из сообщения <b>{who}</b>:"))

        self._text_edit = QTextEdit(selected_text)
        self._text_edit.setMaximumHeight(150)
        self._text_edit.setStyleSheet(
            "QTextEdit { color: #000000; background-color: #ffffff; }"
        )
        layout.addWidget(self._text_edit)

        layout.addWidget(QLabel("Это о чём?"))

        self._category_combo = QComboBox()
        for key, label in _CATEGORIES:
            self._category_combo.addItem(label, key)
        layout.addWidget(self._category_combo)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("✅ Запомнить")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self.setStyleSheet(app_stylesheet())

    @property
    def fact_key(self) -> str:
        return self._category_combo.currentData()

    @property
    def fact_value(self) -> str:
        return self._text_edit.toPlainText().strip()
