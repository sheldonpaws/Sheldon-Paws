from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from gui.styles import app_stylesheet
from config import PALETTE


class FactDialog(QDialog):
    """Диалог подтверждения факта: показать, дать отредактировать, запомнить или отклонить."""

    def __init__(self, key: str, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Шелдон Павс — запомнить? 🧠")
        self.setMinimumWidth(420)
        self._key = key
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        prompt = QLabel(f"Я заметил, ты упомянул <b>{label}</b>:")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self._value_edit = QLineEdit(value)
        self._value_edit.selectAll()
        self._value_edit.setStyleSheet(
            "QLineEdit { color: #000000; background-color: #ffffff; }"
        )
        layout.addWidget(self._value_edit)

        note = QLabel("Можешь отредактировать, если хочешь уточнить.")
        note.setStyleSheet(f"color: {PALETTE['text_light']}; font-size: 12px;")
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("✅ Запомнить")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.clicked.connect(self.accept)

        skip_btn = QPushButton("Не надо")
        skip_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        skip_btn.clicked.connect(self.reject)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(skip_btn)
        layout.addLayout(btn_row)

        self.setStyleSheet(app_stylesheet())

    @property
    def fact_value(self) -> str:
        return self._value_edit.text().strip()

    @property
    def fact_key(self) -> str:
        return self._key
