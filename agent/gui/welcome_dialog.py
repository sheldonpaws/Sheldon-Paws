from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from config import PALETTE


class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Шелдон Павс — Знакомство")
        self.setFixedSize(480, 280)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {PALETTE['bg_main']};
                color: {PALETTE['text_primary']};
            }}
            QLabel {{
                color: {PALETTE['text_primary']};
                font-size: 14px;
            }}
            QLineEdit {{
                background-color: {PALETTE['input_bg']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 14px;
                min-width: 200px;
            }}
            QPushButton {{
                background-color: {PALETTE['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {PALETTE['accent_dark']};
            }}
            QPushButton:disabled {{
                background-color: {PALETTE['toolbar_dark']};
            }}
        """)

        greeting = QLabel("Приветствую! Меня зовут Шелдон Павс. А тебя?")
        greeting.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        greeting.setWordWrap(True)
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)
        prefix = QLabel("Меня зовут")
        prefix.setFont(QFont("Segoe UI", 14))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("введи своё имя")
        self._name_input.setMinimumWidth(200)
        name_layout.addStretch()
        name_layout.addWidget(prefix)
        name_layout.addWidget(self._name_input)
        name_layout.addStretch()

        self._btn = QPushButton("Приятно познакомиться")
        self._btn.setEnabled(False)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self.accept)

        self._name_input.textChanged.connect(self._on_text_changed)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)
        main_layout.addWidget(greeting)
        main_layout.addLayout(name_layout)
        main_layout.addStretch()
        main_layout.addWidget(self._btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_text_changed(self, text: str):
        self._btn.setEnabled(bool(text.strip()))

    def name(self) -> str:
        return self._name_input.text().strip()
