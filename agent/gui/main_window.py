"""
Главное окно приложения — координация всех компонентов.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QLabel, QWidget, QVBoxLayout,
    QToolBar, QFileDialog, QComboBox, QInputDialog,
    QToolButton, QPushButton, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, QTimer, QByteArray, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont, QCursor

from config import AgentConfig, PALETTE, AVAILABLE_MODELS
from llm_client import LLMClient
from secrets import SecretsService
from system_prompt import build_system_prompt
from memory.manager import MemoryManager
from skills.registry import SkillRegistry
from tools.file_reader import FileReaderTool
from gui.chat_widget import ChatWidget
from gui.styles import app_stylesheet
from gui.welcome_dialog import WelcomeDialog
from memory.fact_extractor import detect_facts, save_fact
from gui.fact_dialog import FactDialog
from gui.remember_dialog import RememberDialog


class StreamWorker(QObject):
    """Воркер для потокового получения ответа от LLM."""
    token_received = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, llm: LLMClient, messages: list[dict]):
        super().__init__()
        self._llm = llm
        self._messages = messages

    def run(self):
        try:
            for token in self._llm.chat_stream(self._messages):
                self.token_received.emit(token)
            self.finished.emit()
        except RuntimeError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Ошибка API: {e}")


def make_app_icon() -> QIcon:
    """Иконка приложения: голова добермана из assets."""
    from paths import ASSETS_DIR
    png_path = ASSETS_DIR / "doberman.png"
    if png_path.exists():
        pixmap = QPixmap(str(png_path))
        if not pixmap.isNull():
            return QIcon(pixmap)

    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    accent = QColor(PALETTE["accent"])
    darker = QColor(PALETTE["accent_dark"])

    # Внешний ободок
    painter.setBrush(darker)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)

    # Внутренний круг
    painter.setBrush(accent)
    painter.drawEllipse(4, 4, size - 8, size - 8)

    # Буква S по центру
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", 32, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")

    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    """Главное окно агента Шелдона Павса."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Шелдон Павс — Агент")
        self.setWindowIcon(make_app_icon())
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        # Инициализация компонентов
        self._config = AgentConfig.load()
        # Подхватить ключ из системного хранилища (Credential Manager)
        self._config.api_key = SecretsService.get_api_key()
        self._llm = LLMClient(self._config)
        self._memory = MemoryManager()
        self._skill_registry = SkillRegistry(self._config)
        self._file_reader = FileReaderTool()
        self._stream_thread: QThread | None = None
        self._stream_worker: StreamWorker | None = None
        self._awaiting_introduction = False

        # Восстановить загруженные файлы
        for fname in self._config.loaded_files:
            from pathlib import Path
            fpath = Path(fname)
            if fpath.exists():
                self._file_reader.read_file(str(fpath))

        # Загрузить последнюю сессию
        sessions = self._memory.dialog.list_sessions()
        session_loaded = False
        if sessions:
            self._memory.dialog.load_session(sessions[0]["id"])
            session_loaded = True

        self._setup_ui()
        self._connect_signals()

        if session_loaded:
            self._status_label.setText(f"Сессия: {sessions[0]['id']}")

        # Восстановить сообщения в чате
        history = self._memory.dialog.get_messages_for_api(max_messages=1000)
        if history:
            self._chat.restore_from_history(history)

        # Заполнить список сессий
        self._refresh_sessions()

        # Заполнить список моделей
        self._refresh_model_combo()

        # Приветствие при первом запуске
        QTimer.singleShot(300, self._show_welcome)

    def _setup_ui(self):
        self.setStyleSheet(app_stylesheet())

        # Тулбар
        toolbar = QToolBar("Панель")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {PALETTE['toolbar']}, stop:1 {PALETTE['toolbar_dark']});
                border-bottom: 2px solid {PALETTE['accent_dark']};
                padding: 2px 4px;
                spacing: 4px;
            }}
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 10px;
                color: {PALETTE['text_primary']};
                font-size: 13px;
            }}
            QToolButton:hover {{
                background-color: rgba(148, 120, 182, 0.15);
                border-color: {PALETTE['accent']};
            }}
            QMenu {{
                background-color: {PALETTE['bg_light']};
                border: 1px solid {PALETTE['border']};
                border-radius: 8px;
                padding: 4px;
                max-height: 300px;
            }}
            QMenu::item {{
                padding: 5px 20px 5px 12px;
                min-height: 22px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: rgba(148, 120, 182, 0.2);
                color: {PALETTE['gold']};
            }}
            QMenu::item:disabled {{
                color: {PALETTE['text_light']};
                font-weight: bold;
                background-color: transparent;
            }}
        """)
        self.addToolBar(toolbar)

        # ── Сессии ──
        self._session_btn = QToolButton()
        self._session_btn.setText("Сессия")
        self._session_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._session_menu = QMenu(self)
        self._session_menu.setToolTipsVisible(True)
        self._session_btn.setMenu(self._session_menu)
        self._session_btn.setMinimumWidth(160)
        toolbar.addWidget(self._session_btn)

        rename_action = QAction("✏️", self)
        rename_action.setToolTip("Переименовать сессию")
        rename_action.triggered.connect(self._on_rename_session)
        toolbar.addAction(rename_action)

        new_session_action = QAction("➕", self)
        new_session_action.setToolTip("Новая сессия")
        new_session_action.triggered.connect(self._on_new_session)
        toolbar.addAction(new_session_action)

        delete_session_action = QAction("🗑️", self)
        delete_session_action.setToolTip("Удалить текущую сессию")
        delete_session_action.triggered.connect(self._on_delete_session)
        toolbar.addAction(delete_session_action)

        toolbar.addSeparator()

        # ── Ключ API ──
        self._api_btn = QToolButton()
        self._api_btn.setText("🔑 API")
        self._api_btn.setToolTip("Настроить API-ключ GPTunnel")
        self._api_btn.clicked.connect(self._on_api_key_click)
        toolbar.addWidget(self._api_btn)

        # ── Модель ──
        self._model_btn = QToolButton()
        self._model_btn.setText("Модель")
        self._model_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._model_menu = QMenu(self)
        self._model_btn.setMenu(self._model_menu)
        self._model_btn.setMinimumWidth(140)
        toolbar.addWidget(self._model_btn)

        # ── Навыки ──
        self._skills_btn = QToolButton()
        self._skills_btn.setText("💼 Навыки")
        self._skills_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._skills_menu = QMenu(self)
        self._skills_btn.setMenu(self._skills_menu)
        self._rebuild_skills_menu()
        toolbar.addWidget(self._skills_btn)

        toolbar.addSeparator()

        # ── Файл ──
        file_action = QAction("📎", self)
        file_action.setToolTip("Загрузить файл (.txt, .md)")
        file_action.triggered.connect(self._on_load_file)
        toolbar.addAction(file_action)

        # Центральный виджет — чат на весь экран
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._chat = ChatWidget()
        layout.addWidget(self._chat)
        self.setCentralWidget(central)

        # Статус-бар
        self._status_label = QLabel("Готов к работе")
        self._status_label.setObjectName("status_bar")
        self.statusBar().addWidget(self._status_label, stretch=1)
        self.statusBar().setStyleSheet(
            f"background-color: {PALETTE['toolbar_dark']}; "
            f"color: {PALETTE['text_primary']}; "
            f"border-top: 1px solid {PALETTE['border']};"
        )

        # Обновить состояние ключа
        self._update_api_status()

    def _connect_signals(self):
        self._chat.send_message.connect(self._on_user_message)
        self._chat.remember_requested.connect(self._on_remember_requested)
        self._chat.regenerate_requested.connect(self._on_regenerate_requested)

    def _update_api_status(self):
        key = self._config.api_key or SecretsService.get_api_key()
        if key:
            self._config.api_key = key
            self._api_btn.setText("✅ API")
            self._api_btn.setToolTip("API-ключ сохранён. Нажми чтобы сменить.")
        else:
            self._api_btn.setText("🔑 API")
            self._api_btn.setToolTip("Нажми чтобы ввести API-ключ GPTunnel")

    def _on_api_key_click(self):
        key = self._config.api_key or SecretsService.get_api_key()
        if key:
            msg = QMessageBox(self)
            msg.setWindowTitle("API-ключ")
            msg.setText("✅ Ключ сохранён в системном хранилище.")
            msg.setInformativeText("Хочешь сменить или удалить ключ?")
            change_btn = msg.addButton("Сменить", QMessageBox.ButtonRole.ActionRole)
            clear_btn = msg.addButton("Удалить", QMessageBox.ButtonRole.DestructiveRole)
            msg.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == change_btn:
                self._prompt_api_key()
            elif msg.clickedButton() == clear_btn:
                SecretsService.set_api_key("")
                self._config.api_key = ""
                self._llm.set_api_key("")
                self._update_api_status()
                self._status_label.setText("API-ключ удалён")
        else:
            self._prompt_api_key()

    def _prompt_api_key(self):
        key, ok = QInputDialog.getText(
            self, "API-ключ GPTunnel", "Вставь API-ключ:", text="",
        )
        if not ok or not key.strip():
            return
        key = key.strip()
        SecretsService.set_api_key(key)
        self._config.api_key = key
        self._llm.set_api_key(key)
        self._update_api_status()
        self._status_label.setText("✅ API-ключ сохранён")
        self._refresh_model_combo()

    def _show_welcome(self):
        name = self._memory.facts.get_user_fact("name")
        if name:
            return
        dialog = WelcomeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.name()
            self._memory.facts.set_user_fact("name", name)
            self._memory.save_all()
            self._show_welcome_after_name(name)

    def _show_welcome_after_name(self, name: str):
        """После знакомства: «Взаимно» + инструкция API-ключа в одном диалоге."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Шелдон Павс")
        dlg.setMinimumWidth(480)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)

        greeting = QLabel(f"<h2>Взаимно, {name}! 🐾</h2>")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(greeting)

        hint = QLabel(
            "Теперь нужно настроить API-ключ, чтобы я мог отвечать на вопросы.\n"
            "Без него я не смогу работать."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Кнопка «Показать инструкцию» (исчезает после нажатия)
        show_btn = QPushButton("📖 Показать инструкцию")
        show_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout.addWidget(show_btn)

        # Контейнер с инструкцией (скрыт до нажатия)
        instr_widget = QWidget()
        instr_layout = QVBoxLayout(instr_widget)
        instr_layout.setContentsMargins(0, 0, 0, 0)
        instr_text = QLabel(
            "1. Перейди по ссылке: "
            "<a href='https://gptunnel.ru/?ref=Sheldon_Paws'>gptunnel.ru</a><br><br>"
            "2. В левом нижнем углу нажми «Зарегистрироваться/Войти»<br>"
            "   ⚠️ При входе через Яндекс — авторизуется текущий аккаунт.<br><br>"
            "3. Нажми на аватар → API → «Создать»<br><br>"
            "4. Введи название ключа → «Создать ключ» → скопируй ключ.<br><br>"
            "5. Пополни баланс.<br><br>"
            "<b>🔐 Сохрани ключ в надёжное место, а потом вставь сюда.</b>"
        )
        instr_text.setWordWrap(True)
        instr_text.setOpenExternalLinks(True)
        instr_layout.addWidget(instr_text)

        # Кнопка «ОК, у меня есть ключ» (появляется после инструкции)
        ok_btn = QPushButton("ОК, у меня есть ключ")
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        instr_widget.setVisible(False)
        ok_btn.setVisible(False)
        layout.addWidget(instr_widget)
        layout.addWidget(ok_btn)

        show_btn.clicked.connect(lambda: (
            show_btn.setVisible(False),
            instr_widget.setVisible(True),
            ok_btn.setVisible(True),
        ))
        ok_btn.clicked.connect(dlg.accept)

        dlg.setStyleSheet(app_stylesheet())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if not (self._config.api_key or SecretsService.get_api_key()):
                self._prompt_api_key()
            if self._config.api_key or SecretsService.get_api_key():
                self._show_model_selection()

    def _show_model_selection(self):
        """Диалог выбора модели после сохранения API-ключа."""
        models = self._llm.list_models() if self._llm.is_connected else AVAILABLE_MODELS
        if not models:
            self._start_introduction()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Шелдон Павс — выбор модели")
        dlg.setMinimumWidth(400)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        label = QLabel(
            "Отлично, ключ сохранён! 🎉\n\n"
            "Теперь выбери модель, с которой я буду работать:"
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        combo = QComboBox()
        for m in models:
            display = f"{m['name']}  ({m['id']})" if " " in m['name'] else m['name']
            combo.addItem(display, m['id'])
        if self._config.model:
            idx = combo.findData(self._config.model)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        layout.addWidget(combo)

        ok_btn = QPushButton("Давай начнём! 🐾")
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.clicked.connect(dlg.accept)
        layout.addWidget(ok_btn)

        dlg.setStyleSheet(app_stylesheet())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            model_id = combo.currentData()
            if model_id:
                self._on_model_menu_selected(model_id)
            self._start_introduction()

    def _start_introduction(self):
        """Создать сессию «Знакомство», отправить скрытый промпт и запустить LLM."""
        session_id = self._memory.new_session("Знакомство", self._config.model)
        self._memory.save_all()
        self._refresh_sessions()
        self._chat.clear_chat()

        # Скрытый промпт — пользователь его не видит
        hidden_prompt = "Расскажи о себе. А теперь спроси пользователя о нём."
        self._memory.dialog.add_message("user", hidden_prompt)

        # Собрать контекст
        name = self._memory.facts.get_user_fact("name") or ""
        context_md = self._memory.get_full_context(user_query=hidden_prompt)
        files_content = self._file_reader.get_all_content()
        system_prompt = build_system_prompt(
            config=self._config,
            context_md=context_md,
            loaded_files_content=files_content,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._memory.dialog.get_messages_for_api(max_messages=30))

        # Запустить streaming ответа
        self._chat.start_assistant_message()
        self._chat.set_enabled(False)
        self._status_label.setText("Шелдон думает... 🐾")

        self._stream_thread = QThread()
        self._stream_worker = StreamWorker(self._llm, messages)
        self._stream_worker.moveToThread(self._stream_thread)

        self._stream_thread.started.connect(self._stream_worker.run)
        self._stream_worker.token_received.connect(self._chat.append_assistant_text)
        self._stream_worker.finished.connect(self._on_introduction_finished)
        self._stream_worker.error.connect(self._on_stream_error)
        self._stream_worker.finished.connect(self._stream_thread.quit)
        self._stream_worker.error.connect(self._stream_thread.quit)

        self._stream_thread.start()

    def _on_introduction_finished(self):
        """Завершить знакомство: сохранить ответ, включить ввод, ждать пользователя."""
        self._chat.finish_assistant_message()
        self._chat.set_enabled(True)
        self._status_label.setText("Готов к работе")

        last_bubble = self._chat._messages[-1] if self._chat._messages else None
        if last_bubble and last_bubble._role == "assistant":
            self._memory.dialog.add_message("assistant", last_bubble.text)
        self._memory.save_all()
        self._awaiting_introduction = True

    def _rebuild_skills_menu(self):
        self._skills_menu.clear()
        for skill in self._skill_registry.all_skills:
            action = self._skills_menu.addAction(skill.display_name)
            action.setCheckable(True)
            action.setChecked(skill.active)
            action.toggled.connect(lambda checked, name=skill.name: self._on_skill_toggled(name, checked))

    def _on_load_file(self):
        """Загрузить файл через диалог."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Загрузить файл", "",
            "Текстовые файлы (*.txt *.md);;Все файлы (*)"
        )
        if not filepath:
            return
        try:
            name = self._file_reader.read_file(filepath)
            self._status_label.setText(f"Файл загружен: {name}")
        except ValueError as e:
            self._status_label.setText(f"Ошибка: {e}")

    def _on_user_message(self, text: str):
        if not self._llm.is_connected:
            self._chat.add_assistant_message(
                "⚠️ Сначала задай API ключ GPTunnel — нажми кнопку «🔑 API» в тулбаре."
            )
            return

        # Добавить в чат
        self._chat.add_user_message(text)

        # Сохранить в память
        self._memory.dialog.add_message("user", text)

        # Если это ответ на знакомство — сохранить данные пользователя
        if self._awaiting_introduction:
            self._awaiting_introduction = False
            self._memory.facts.set_user_fact("about", text[:1000])
            self._memory.save_all()

        # Собрать system prompt
        context_md = self._memory.get_full_context(user_query=text)
        files_content = self._file_reader.get_all_content()
        system_prompt = build_system_prompt(
            config=self._config,
            context_md=context_md,
            loaded_files_content=files_content,
        )

        # Собрать сообщения для API
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._memory.dialog.get_messages_for_api(max_messages=30))

        # Начать streaming
        self._chat.start_assistant_message()
        self._chat.set_enabled(False)
        self._status_label.setText("Шелдон думает... 🐾")

        self._stream_thread = QThread()
        self._stream_worker = StreamWorker(self._llm, messages)
        self._stream_worker.moveToThread(self._stream_thread)

        self._stream_thread.started.connect(self._stream_worker.run)
        self._stream_worker.token_received.connect(self._chat.append_assistant_text)
        self._stream_worker.finished.connect(self._on_stream_finished)
        self._stream_worker.error.connect(self._on_stream_error)
        self._stream_worker.finished.connect(self._stream_thread.quit)
        self._stream_worker.error.connect(self._stream_thread.quit)

        self._stream_thread.start()

    def _on_stream_finished(self):
        self._chat.finish_assistant_message()
        self._chat.set_enabled(True)
        self._status_label.setText("Готов к работе")

        # Сохранить ответ в память
        last_bubble = self._chat._messages[-1] if self._chat._messages else None
        if last_bubble and last_bubble._role == "assistant":
            self._memory.dialog.add_message("assistant", last_bubble.text)

        # Предложить сохранить факты из последнего сообщения пользователя
        session = self._memory.dialog._current_session
        if session:
            for msg in reversed(session):
                if msg["role"] == "user":
                    facts = detect_facts(msg["content"], self._memory.facts)
                    for f in facts:
                        dlg = FactDialog(f["key"], f["label"], f["value"], self)
                        if dlg.exec() == QDialog.DialogCode.Accepted:
                            save_fact(f["key"], dlg.fact_value, self._memory.facts)
                            self._status_label.setText(f"Запомнил: {f['label']}")
                    break

        self._memory.save_all()

    def _on_remember_requested(self, role: str, text: str):
        """Обработать ручное сохранение выделенного текста."""
        dlg = RememberDialog(role, text, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            key = dlg.fact_key
            value = dlg.fact_value
            if key == "preference":
                self._memory.facts.set_preference(
                    f"custom_{len(self._memory.facts.get_all_preferences())}", value
                )
            elif key == "other":
                context_all = self._memory.facts.get_all_context()
                self._memory.facts.set_context(
                    f"note_{len(context_all)}", value
                )
            else:
                self._memory.facts.set_user_fact(key, value)
            self._memory.save_all()
            self._status_label.setText(f"✅ Запомнил: {value[:40]}...")

    def _on_regenerate_requested(self, old_text: str, new_text: str):
        """Заменить сообщение в диалоге и перегенерировать ответ."""
        session = self._memory.dialog._current_session
        if not session:
            return

        found = -1
        for i, m in enumerate(session):
            if m["role"] == "user" and m["content"].rstrip() == old_text.rstrip():
                found = i
                break
        if found < 0:
            return

        session[found]["content"] = new_text

        if found + 1 < len(session) and session[found + 1]["role"] == "assistant":
            del session[found + 1]

        bubbles = self._chat._messages
        for i, b in enumerate(bubbles):
            if b._role == "user" and b._text.rstrip() == old_text.rstrip():
                b._text = new_text
                b._text_label.setText(new_text)
                if i + 1 < len(bubbles) and bubbles[i + 1]._role == "assistant":
                    bubbles[i + 1].deleteLater()
                    del bubbles[i + 1]
                break

        self._memory.save_all()

        self._chat.start_assistant_message()
        self._chat.set_enabled(False)
        self._status_label.setText("Шелдон думает... 🐾")

        context_md = self._memory.get_full_context(user_query=new_text)
        files_content = self._file_reader.get_all_content()
        system_prompt = build_system_prompt(
            config=self._config,
            context_md=context_md,
            loaded_files_content=files_content,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._memory.dialog.get_messages_for_api(max_messages=30))

        self._stream_thread = QThread()
        self._stream_worker = StreamWorker(self._llm, messages)
        self._stream_worker.moveToThread(self._stream_thread)

        self._stream_thread.started.connect(self._stream_worker.run)
        self._stream_worker.token_received.connect(self._chat.append_assistant_text)
        self._stream_worker.finished.connect(self._on_stream_finished)
        self._stream_worker.error.connect(self._on_stream_error)
        self._stream_worker.finished.connect(self._stream_thread.quit)
        self._stream_worker.error.connect(self._stream_thread.quit)

        self._stream_thread.start()

    def _on_stream_error(self, error_msg: str):
        self._chat.finish_assistant_message()
        self._chat.add_assistant_message(f"❌ {error_msg}")
        self._chat.set_enabled(True)
        self._status_label.setText("Ошибка")

    def _refresh_model_combo(self):
        saved_id = self._config.model
        models = self._llm.list_models() if self._llm.is_connected else []
        if not models:
            models = AVAILABLE_MODELS

        self._model_menu.clear()
        for m in models:
            action = self._model_menu.addAction(m['name'])
            action.setData(m['id'])
            action.triggered.connect(lambda checked, mid=m['id']: self._on_model_menu_selected(mid))
            if m['id'] == saved_id:
                self._model_btn.setText(m['name'])

        if not self._model_btn.text() or self._model_btn.text() == "Модель":
            found = next((m['name'] for m in models if m['id'] == saved_id), None)
            if found:
                self._model_btn.setText(found)

        if models:
            self._status_label.setText(f"Моделей: {len(models)}")
        elif self._llm.is_connected:
            self._status_label.setText("Не удалось загрузить модели с сервера")

    def _on_model_menu_selected(self, model_id: str):
        if not model_id:
            return
        self._llm.set_model(model_id)
        self._config.model = model_id
        self._config.save()
        # Сохранить модель для текущей сессии
        session_id = self._memory.dialog._current_session_id
        if session_id:
            self._memory.dialog.set_session_model(session_id, model_id)
        model_name = AgentConfig.get_model_name(model_id)
        self._model_btn.setText(model_name.split(" (")[0] if " (" in model_name else model_name)
        self._status_label.setText(f"Модель: {model_name}")

    def _on_skill_toggled(self, skill_name: str, active: bool):
        if active:
            self._skill_registry.activate_skill(skill_name)
        else:
            self._skill_registry.deactivate_skill(skill_name)
        status = "активирован" if active else "деактивирован"
        self._status_label.setText(f"Навык {skill_name} {status}")

    def _on_new_session(self):
        title, ok = QInputDialog.getText(self, "Новая сессия", "Название (можно оставить пустым):")
        if not ok:
            return
        self._memory.save_all()
        self._memory.new_session(title.strip(), self._config.model)
        self._memory.save_all()
        self._chat.clear_chat()
        self._refresh_sessions()
        self._status_label.setText("Новая сессия начата")

    def _on_delete_session(self):
        session_id = self._memory.dialog._current_session_id
        if not session_id:
            self._status_label.setText("Нет сессии для удаления")
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Удалить сессию")
        msg.setText(f"Сессия: {self._memory.dialog.current_title or session_id}")
        msg.setInformativeText("Что сделать с сессией?")
        clear_btn = msg.addButton("Очистить (оставить файл)", QMessageBox.ButtonRole.ActionRole)
        delete_btn = msg.addButton("Удалить с диска", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == clear_btn:
            self._memory.dialog._current_session = []
            self._memory.dialog.save()
            self._chat.clear_chat()
            self._status_label.setText("Сессия очищена")
        elif msg.clickedButton() == delete_btn:
            self._memory.dialog.delete_session(session_id)
            self._chat.clear_chat()
            remaining = self._memory.dialog.list_sessions()
            if remaining:
                self._on_session_selected(remaining[0]["id"])
                self._status_label.setText(f"Сессия удалена, переключено на «{remaining[0]['title']}»")
            else:
                self._memory.new_session(model=self._config.model)
                self._refresh_sessions()
                self._status_label.setText("Все сессии удалены, создана новая")
            self._status_label.setText("Сессия удалена с диска")
        self._refresh_sessions()

    def _refresh_sessions(self):
        self._session_menu.clear()
        sessions = self._memory.dialog.list_sessions()
        current_id = self._memory.dialog._current_session_id
        for s in sessions:
            preview = s.get("preview", "")
            label = s["title"] if s["title"] != s["id"] else s["title"][:19]
            if preview:
                action = self._session_menu.addAction(f"{label} — {preview}")
            else:
                action = self._session_menu.addAction(label)
            action.setData(s["id"])
            action.triggered.connect(lambda checked, sid=s["id"]: self._on_session_selected(sid))
            if s["id"] == current_id:
                self._session_btn.setText(label)

        if not sessions:
            self._session_btn.setText("Нет сессий")
        elif not self._session_btn.text() or self._session_btn.text() == "Нет сессий":
            self._session_btn.setText(sessions[0]["title"] if sessions[0]["title"] != sessions[0]["id"] else sessions[0]["id"][:19])

    def _on_session_selected(self, session_id: str):
        if not session_id or session_id == self._memory.dialog._current_session_id:
            return
        self._generate_session_summary()
        self._memory.save_all()
        if self._memory.dialog.load_session(session_id):
            self._chat.clear_chat()
            history = self._memory.dialog.get_messages_for_api(max_messages=1000)
            if history:
                self._chat.restore_from_history(history)
            title = self._memory.dialog.current_title or session_id
            self._session_btn.setText(title[:25])
            self._status_label.setText(f"Сессия: {title}")
            # Восстановить модель сессии (не трогая config.model)
            session_model = self._memory.dialog.get_session_model(session_id)
            if session_model and session_model != self._config.model:
                self._llm.set_model(session_model)
                model_name = AgentConfig.get_model_name(session_model)
                self._model_btn.setText(model_name.split(" (")[0] if " (" in model_name else model_name)

    def _generate_session_summary(self):
        messages = self._memory.dialog._current_session
        if not messages:
            return
        user_msgs = [m for m in messages if m["role"] == "user"]
        asst_msgs = [m for m in messages if m["role"] == "assistant"]
        if not user_msgs and not asst_msgs:
            return
        lines = []
        if user_msgs:
            lines.append(f"Пользователь: {user_msgs[0]['content'][:200]}")
        if asst_msgs:
            lines.append(f"Шелдон: {asst_msgs[-1]['content'][:200]}")
        summary = "\n\n".join(lines)
        self._memory.dialog.save_session_summary(summary, self._memory.dialog._current_session_id)

    def _on_rename_session(self):
        current = self._memory.dialog.current_title or self._memory.dialog._current_session_id
        new_title, ok = QInputDialog.getText(
            self, "Переименовать сессию",
            "Новое название:", text=current
        )
        if not ok:
            return
        self._memory.dialog.rename_session(
            self._memory.dialog._current_session_id, new_title.strip()
        )
        self._refresh_sessions()

    def closeEvent(self, event):
        self._memory.save_all()
        # Сохранить загруженные файлы в конфиг
        self._config.loaded_files = list(self._file_reader.loaded_filenames)
        self._config.save()
        super().closeEvent(event)
