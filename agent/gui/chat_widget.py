"""
Виджет чата — отображение сообщений и ввод.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeyEvent, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QTextEdit, QPushButton, QSizePolicy, QMenu, QApplication,
)

from gui.styles import PALETTE


class MessageBubble(QWidget):
    """Пузырь одного сообщения."""

    remember_requested = pyqtSignal(str, str)  # role, selected_text
    regenerate_requested = pyqtSignal(object, str)  # сам пузырь, новый текст

    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self._role = role
        self._text = text
        # Индекс сообщения в текущей сессии истории (None — сообщение
        # не сохранено в историю, например служебное уведомление).
        self.history_index: int | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._setup_ui()

    @property
    def role(self) -> str:
        """Роль сообщения: «user» или «assistant»."""
        return self._role

    def set_text(self, text: str):
        """Заменить текст пузыря (и в режиме просмотра, и в данных)."""
        self._text = text
        self._text_label.setText(text)
        self._text_edit.setPlainText(text)

    def set_actions_enabled(self, enabled: bool):
        """Включить/выключить кнопки редактирования пузыря."""
        if self._role == "user":
            self._edit_btn.setEnabled(enabled)
        self._send_edit_btn.setEnabled(enabled)

    def _setup_ui(self):
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(2)

        # Верхняя строка: имя + кнопка редактирования
        sender = "Ты" if self._role == "user" else "🐾 Шелдон"
        header = QHBoxLayout()
        header.setSpacing(4)

        sender_label = QLabel(sender)
        sender_label.setObjectName("sender_label")
        header.addWidget(sender_label)
        header.addStretch()

        if self._role == "user":
            self._edit_btn = QPushButton("✏️")
            self._edit_btn.setFixedSize(24, 24)
            self._edit_btn.setToolTip("Редактировать")
            self._edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._edit_btn.clicked.connect(self._enter_edit_mode)
            header.addWidget(self._edit_btn)

        self._outer_layout.addLayout(header)

        # Текст (QLabel) — режим просмотра
        self._text_label = QLabel(self._text)
        self._text_label.setObjectName("message_label")
        self._text_label.setWordWrap(True)
        self._text_label.setTextFormat(Qt.TextFormat.PlainText)
        self._text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._text_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._text_label.customContextMenuRequested.connect(self._show_context_menu)
        self._text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._outer_layout.addWidget(self._text_label)

        # Редактор (QTextEdit) — режим редактирования
        self._text_edit = QTextEdit(self._text)
        self._text_edit.setMaximumHeight(150)
        self._text_edit.setStyleSheet(
            "QTextEdit { color: #000000; background-color: #ffffff; }"
        )
        self._text_edit.setVisible(False)
        self._outer_layout.addWidget(self._text_edit)

        # Кнопка отправки в режиме редактирования
        self._send_edit_btn = QPushButton("✅ Отправить")
        self._send_edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._send_edit_btn.setVisible(False)
        self._send_edit_btn.clicked.connect(self._on_edit_send)
        self._outer_layout.addWidget(self._send_edit_btn)

    def _enter_edit_mode(self):
        self._edit_btn.setVisible(False)
        self._text_label.setVisible(False)
        self._text_edit.setPlainText(self._text)
        self._text_edit.setVisible(True)
        self._send_edit_btn.setVisible(True)
        self._text_edit.setFocus()

    def _on_edit_send(self):
        new_text = self._text_edit.toPlainText().strip()
        if not new_text or new_text == self._text:
            self._exit_edit_mode()
            return
        # Текст пузыря уже обновлён здесь, поэтому сигнал несёт сам объект
        # пузыря, а не старую строку — иначе поиск по тексту не находит его.
        self.set_text(new_text)
        self._exit_edit_mode()
        self.regenerate_requested.emit(self, new_text)

    def _exit_edit_mode(self):
        self._text_edit.setVisible(False)
        self._send_edit_btn.setVisible(False)
        self._text_label.setVisible(True)
        self._edit_btn.setVisible(True)

    def _show_context_menu(self, pos):
        selected = self._text_label.selectedText()
        menu = QMenu(self)
        if selected:
            act = menu.addAction("🧠 Запомнить")
            act.triggered.connect(lambda: self.remember_requested.emit(
                self._role, selected
            ))
        menu.addAction("📋 Копировать", self._copy_selection)
        menu.exec(self._text_label.mapToGlobal(pos))

    def _copy_selection(self):
        selected = self._text_label.selectedText()
        if selected:
            QApplication.clipboard().setText(selected)

    def append_text(self, text: str):
        self._text += text
        self._text_label.setText(self._text)

    @property
    def text(self) -> str:
        return self._text


class InputField(QTextEdit):
    """Поле ввода с поддержкой Ctrl+Enter для отправки."""

    send_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("input_field")
        self.setPlaceholderText("Напиши Шелдону... (Ctrl+Enter — отправить)")
        self.setMaximumHeight(120)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAcceptRichText(False)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ChatWidget(QWidget):
    """Виджет чата: отображение сообщений + поле ввода."""

    send_message = pyqtSignal(str)
    remember_requested = pyqtSignal(str, str)  # role, text
    regenerate_requested = pyqtSignal(object, str)  # пузырь, новый текст

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages: list[MessageBubble] = []
        self._current_assistant_bubble: MessageBubble | None = None
        self._scroll_pending = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setObjectName("chat_area")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet(f"background-color: {PALETTE['bg_main']};")

        self._messages_container = QWidget()
        self._messages_container.setStyleSheet("background: transparent;")
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._messages_layout.setSpacing(6)
        self._messages_layout.addStretch()

        scroll.setWidget(self._messages_container)
        layout.addWidget(scroll, stretch=1)
        self._scroll_area = scroll

        # Поле ввода + кнопка
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = InputField()
        self._input.send_requested.connect(self._on_send)
        input_row.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("Отправить")
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        layout.addLayout(input_row)

    # ── Публичный доступ к сообщениям ─────────────────────────

    @property
    def messages(self) -> list[MessageBubble]:
        """Список пузырей в порядке отображения."""
        return list(self._messages)

    def last_message(self) -> MessageBubble | None:
        """Последний пузырь (или None, если сообщений нет)."""
        return self._messages[-1] if self._messages else None

    def index_of(self, bubble: MessageBubble) -> int:
        """Позиция пузыря в списке (-1 если не найден)."""
        try:
            return self._messages.index(bubble)
        except ValueError:
            return -1

    def remove_message_after(self, bubble: MessageBubble):
        """Удалить пузырь, следующий за указанным (если он assistant)."""
        i = self.index_of(bubble)
        if i < 0 or i + 1 >= len(self._messages):
            return
        nxt = self._messages[i + 1]
        if nxt.role != "assistant":
            return
        del self._messages[i + 1]
        self._messages_layout.removeWidget(nxt)
        nxt.deleteLater()

    def discard_last_message(self):
        """Удалить последний пузырь (например, пустой ответ при ошибке)."""
        if not self._messages:
            return
        bubble = self._messages.pop()
        self._messages_layout.removeWidget(bubble)
        if self._current_assistant_bubble is bubble:
            self._current_assistant_bubble = None
        bubble.deleteLater()

    def shift_history_indices(self, from_index: int, delta: int):
        """Сдвинуть привязку пузырей к истории начиная с from_index."""
        for b in self._messages:
            if b.history_index is not None and b.history_index >= from_index:
                b.history_index += delta

    # ── Работа с сообщениями ──────────────────────────────────

    def _connect_bubble(self, bubble: MessageBubble):
        bubble.remember_requested.connect(self.remember_requested)
        bubble.regenerate_requested.connect(self.regenerate_requested)

    def restore_from_history(self, messages: list[dict], start_index: int = 0):
        if not messages:
            return
        for offset, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            bubble = MessageBubble(role, content)
            bubble.history_index = start_index + offset
            self._connect_bubble(bubble)
            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, bubble)
            self._messages.append(bubble)
        self._scroll_to_bottom()

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.send_message.emit(text)

    def add_user_message(self, text: str) -> MessageBubble:
        bubble = MessageBubble("user", text)
        self._connect_bubble(bubble)
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, bubble)
        self._messages.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def start_assistant_message(self) -> MessageBubble:
        bubble = MessageBubble("assistant", "")
        self._connect_bubble(bubble)
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, bubble)
        self._messages.append(bubble)
        self._current_assistant_bubble = bubble
        self._scroll_to_bottom()
        return bubble

    def append_assistant_text(self, text: str):
        if self._current_assistant_bubble:
            self._current_assistant_bubble.append_text(text)
            self._scroll_to_bottom()

    def finish_assistant_message(self):
        self._current_assistant_bubble = None

    def add_assistant_message(self, text: str) -> MessageBubble:
        bubble = MessageBubble("assistant", text)
        self._connect_bubble(bubble)
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, bubble)
        self._messages.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def clear_chat(self):
        for msg in self._messages:
            msg.deleteLater()
        self._messages.clear()
        self._current_assistant_bubble = None

    def _scroll_to_bottom(self):
        # Не плодим таймеры на каждый токен: пока таймер висит — пропускаем.
        if self._scroll_pending:
            return
        self._scroll_pending = True
        QTimer.singleShot(50, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self):
        self._scroll_pending = False
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_enabled(self, enabled: bool):
        """Включить/выключить ввод и кнопки редактирования пузырей."""
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        for bubble in self._messages:
            bubble.set_actions_enabled(enabled)
