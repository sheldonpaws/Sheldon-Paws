"""
Главное окно приложения — координация всех компонентов.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QLabel, QWidget, QVBoxLayout,
    QToolBar, QFileDialog, QComboBox, QInputDialog, QLineEdit,
    QToolButton, QPushButton, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont, QCursor

from config import AgentConfig, PALETTE, AVAILABLE_MODELS
from llm_client import LLMClient
from app_secrets import SecretsService
from system_prompt import build_system_prompt
from memory.manager import MemoryManager
from skills.registry import SkillRegistry
from skills.skill_writer import SkillStreamFilter, extract_skill_blocks, write_skill
from tools.file_reader import FileReaderTool
from gui.chat_widget import ChatWidget
from gui.styles import app_stylesheet
from gui.welcome_dialog import WelcomeDialog
from memory.fact_extractor import detect_facts, save_fact
from gui.fact_dialog import FactDialog
from gui.remember_dialog import RememberDialog
from gui.model_dialog import ModelSelectDialog

# Сколько ждать завершения фонового потока при закрытии приложения, мс.
THREAD_WAIT_MS = 5000


class StreamWorker(QObject):
    """Воркер для потокового получения ответа от LLM."""

    token_received = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, llm: LLMClient, messages: list[dict]):
        super().__init__()
        self._llm = llm
        self._messages = messages
        self._cancelled = False
        # Служебные блоки <skill>…</skill> прячем от пользователя:
        # в чат уходит видимая часть, raw_text — полный ответ модели.
        self._skill_filter = SkillStreamFilter()

    @property
    def raw_text(self) -> str:
        """Полный текст ответа, включая скрытые блоки <skill>."""
        return self._skill_filter.raw

    @property
    def was_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        """Попросить воркер остановиться после текущего токена."""
        self._cancelled = True

    def run(self):
        try:
            for token in self._llm.chat_stream(self._messages):
                if self._cancelled:
                    break
                visible = self._skill_filter.feed(token)
                if visible:
                    self.token_received.emit(visible)
            tail = self._skill_filter.finish()
            if tail and not self._cancelled:
                self.token_received.emit(tail)
            self.finished.emit()
        except RuntimeError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Ошибка API: {e}")


class ModelsWorker(QObject):
    """Фоновая загрузка списка моделей (сетевой запрос вдали от GUI-потока)."""

    done = pyqtSignal(list)

    def __init__(self, llm: LLMClient):
        super().__init__()
        self._llm = llm

    def run(self):
        try:
            models = self._llm.list_models()
        except Exception as e:  # noqa: BLE001 — не роняем GUI из-за сети
            print(f"[Модели] Не удалось загрузить список: {e}")
            models = []
        self.done.emit(models)


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
        self._stream_active = False
        self._models_thread: QThread | None = None
        self._models_worker: ModelsWorker | None = None
        self._models_callbacks: list = []
        self._models_result: list = []
        self._awaiting_introduction = False
        self._closing = False

        # Восстановить загруженные файлы (в конфиге хранятся абсолютные пути)
        for fpath in self._config.loaded_files:
            res = self._file_reader.read_file(fpath, trusted=True)
            if not res.success:
                print(f"[Файлы] Не удалось восстановить «{fpath}»: {res.error}")

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
            start_index = self._memory.dialog.history_start_index(len(history))
            self._chat.restore_from_history(history, start_index=start_index)

        # Заполнить список сессий
        self._refresh_sessions()

        # Заполнить список моделей (сеть — в фоновом потоке)
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
        # Кнопка (не стрелка) открывает модальное окно с поиском и ценами;
        # стрелка по-прежнему показывает быстрое меню из _apply_models.
        self._model_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._model_menu = QMenu(self)
        self._model_btn.setMenu(self._model_menu)
        # Лямбда: сигнал clicked несёт bool — без неё PyQt мог бы
        # передать его в _open_model_dialog как models.
        self._model_btn.clicked.connect(lambda _checked=False: self._open_model_dialog())
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

    # ── API-ключ ──────────────────────────────────────────────

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
                if self._llm.set_api_key(""):
                    self._config.api_key = ""
                    self._update_api_status()
                    self._status_label.setText("API-ключ удалён")
                else:
                    self._status_label.setText(
                        "❌ Не удалось удалить ключ: хранилище недоступно"
                    )
        else:
            self._prompt_api_key()

    def _prompt_api_key(self):
        # Ключ вводится под маской — EchoMode.Password
        key, ok = QInputDialog.getText(
            self, "API-ключ GPTunnel", "Вставь API-ключ:",
            QLineEdit.EchoMode.Password, "",
        )
        if not ok or not key.strip():
            return
        key = key.strip()
        if not self._llm.set_api_key(key):
            self._status_label.setText(
                "❌ Не удалось сохранить ключ: системное хранилище недоступно"
            )
            return
        self._config.api_key = key
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

    # ── Модели ────────────────────────────────────────────────

    def _show_model_selection(self):
        """Диалог выбора модели после сохранения API-ключа.

        Список моделей грузится в фоновом потоке — GUI не блокируется.
        """
        if self._llm.is_connected:
            self._status_label.setText("Загружаю список моделей...")
            self._fetch_models_async(self._show_model_selection_dialog)
        else:
            self._show_model_selection_dialog(AVAILABLE_MODELS)

    def _show_model_selection_dialog(self, models: list[dict]):
        """Первый выбор модели сразу после сохранения API-ключа."""
        if not models:
            models = AVAILABLE_MODELS
        dlg = ModelSelectDialog(
            models,
            current_id=self._config.model,
            subtitle=(
                "Отлично, ключ сохранён! 🎉\n\n"
                "Теперь выбери модель, с которой я буду работать:"
            ),
            parent=self,
        )
        dlg.setStyleSheet(app_stylesheet())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_id:
            self._on_model_menu_selected(dlg.selected_id)
            self._start_introduction()

    def _open_model_dialog(self, models: list[dict] | None = None):
        """Модальное окно выбора модели с поиском и ценами (клик по «Модель»)."""
        if models is None:
            if self._models_result:
                models = self._models_result
            elif self._llm.is_connected:
                self._status_label.setText("Загружаю список моделей...")
                self._fetch_models_async(self._open_model_dialog)
                return
            else:
                models = AVAILABLE_MODELS
        if not models:
            models = AVAILABLE_MODELS
        dlg = ModelSelectDialog(models, current_id=self._llm.model, parent=self)
        dlg.setStyleSheet(app_stylesheet())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_id:
            self._on_model_menu_selected(dlg.selected_id)

    def _fetch_models_async(self, on_done):
        """Загрузить список моделей в фоне; on_done(models) вызовется в GUI-потоке."""
        self._models_callbacks.append(on_done)
        if self._models_thread is not None:
            return  # загрузка уже идёт — колбэк получит её результат
        thread = QThread()
        worker = ModelsWorker(self._llm)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_models_loaded)
        worker.done.connect(thread.quit)
        # Результат отдаём только после полной остановки потока (finished),
        # тогда можно безопасно заменить ссылки и запустить новую загрузку.
        # Слот — метод MainWindow (QObject), поэтому он выполнится в GUI-потоке.
        thread.finished.connect(self._on_models_thread_finished)
        thread.start()
        self._models_thread = thread
        self._models_worker = worker

    def _on_models_loaded(self, models: list):
        self._models_result = models

    def _on_models_thread_finished(self):
        thread = self._models_thread
        self._models_thread = None
        self._models_worker = None
        if thread is not None:
            thread.deleteLater()
        callbacks = self._models_callbacks
        self._models_callbacks = []
        for cb in callbacks:
            cb(self._models_result)

    def _refresh_model_combo(self):
        """Обновить меню моделей: сеть вынесена в фоновый поток."""
        if not self._llm.is_connected:
            self._apply_models([])
            return
        self._status_label.setText("Загружаю список моделей...")
        self._fetch_models_async(self._apply_models)

    def _apply_models(self, models: list[dict]):
        """Заполнить меню моделей полученным списком (может быть пустым)."""
        fetched = bool(models)
        if not models:
            models = AVAILABLE_MODELS
        saved_id = self._config.model

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

        if fetched:
            self._status_label.setText(f"Моделей: {len(models)}")
        elif self._llm.is_connected:
            self._status_label.setText(
                "Не удалось загрузить модели с сервера, показан базовый список"
            )
        else:
            self._status_label.setText(f"Моделей: {len(models)}")

    def _on_model_menu_selected(self, model_id: str):
        if not model_id:
            return
        # persist=True — выбранный пользователем вариант становится глобальным
        self._llm.set_model(model_id, persist=True)
        # Сохранить модель для текущей сессии
        session_id = self._memory.dialog._current_session_id
        if session_id:
            self._memory.dialog.set_session_model(session_id, model_id)
        model_name = AgentConfig.get_model_name(model_id)
        self._model_btn.setText(model_name.split(" (")[0] if " (" in model_name else model_name)
        self._status_label.setText(f"Модель: {model_name}")

    # ── Запуск стриминга ──────────────────────────────────────

    def _is_streaming(self) -> bool:
        """Идёт ли сейчас получение ответа (или поток ещё не остановился)."""
        if self._stream_active:
            return True
        thread = self._stream_thread
        return thread is not None and thread.isRunning()

    def _start_stream(self, messages: list[dict], on_finished) -> bool:
        """Запустить потоковый ответ. False — если предыдущий поток ещё работает."""
        if self._is_streaming():
            self._status_label.setText("Ответ ещё идёт — подожди окончания")
            return False

        self._chat.start_assistant_message()
        # Блокируем ввод И кнопки редактирования/регенерации на пузырях
        self._chat.set_enabled(False)
        self._status_label.setText("Шелдон думает... 🐾")

        thread = QThread()
        worker = StreamWorker(self._llm, messages)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.token_received.connect(self._chat.append_assistant_text)
        worker.finished.connect(on_finished)
        worker.error.connect(self._on_stream_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)

        self._stream_thread = thread
        self._stream_worker = worker
        self._stream_active = True
        thread.start()
        return True

    def _save_last_assistant_reply(self):
        """Сохранить последний ответ в историю сессии с привязкой к пузырю."""
        bubble = self._chat.last_message()
        if bubble is None or bubble.role != "assistant" or not bubble.text.strip():
            return
        bubble.history_index = self._memory.dialog.add_message("assistant", bubble.text)

    # ── Знакомство ────────────────────────────────────────────

    def _start_introduction(self):
        """Создать сессию «Знакомство», отправить скрытый промпт и запустить LLM."""
        if self._is_streaming():
            self._status_label.setText("Ответ ещё идёт — подожди окончания")
            return
        self._memory.new_session("Знакомство", self._config.model)
        self._memory.save_all()
        self._refresh_sessions()
        self._chat.clear_chat()
        self._memory.log_session_event("начата сессия «Знакомство»")

        # Скрытый промпт — пользователь его не видит
        hidden_prompt = "Расскажи о себе. А теперь спроси пользователя о нём."
        self._memory.dialog.add_message("user", hidden_prompt)

        # Собрать контекст
        context_md = self._memory.get_full_context(user_query=hidden_prompt)
        files_content = self._file_reader.get_all_content()
        system_prompt = build_system_prompt(
            config=self._config,
            context_md=context_md,
            loaded_files_content=files_content,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._memory.dialog.get_messages_for_api(max_messages=30))

        self._start_stream(messages, self._on_introduction_finished)

    def _on_introduction_finished(self):
        """Завершить знакомство: сохранить ответ, включить ввод, ждать пользователя."""
        self._stream_active = False
        self._chat.finish_assistant_message()
        self._chat.set_enabled(True)
        self._status_label.setText("Готов к работе")

        self._save_last_assistant_reply()
        self._process_skill_blocks()
        self._memory.save_all()
        self._awaiting_introduction = True

    # ── Навыки ────────────────────────────────────────────────

    def _rebuild_skills_menu(self):
        self._skills_menu.clear()
        for skill in self._skill_registry.all_skills:
            action = self._skills_menu.addAction(skill.display_name)
            action.setCheckable(True)
            action.setChecked(skill.active)
            action.toggled.connect(lambda checked, name=skill.name: self._on_skill_toggled(name, checked))

    def _on_skill_toggled(self, skill_name: str, active: bool):
        if active:
            self._skill_registry.activate_skill(skill_name)
        else:
            self._skill_registry.deactivate_skill(skill_name)
        status = "активирован" if active else "деактивирован"
        self._status_label.setText(f"Навык {skill_name} {status}")

    # ── Файлы ─────────────────────────────────────────────────

    def _on_load_file(self):
        """Загрузить файл через диалог."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Загрузить файл", "",
            "Текстовые файлы (*.txt *.md);;Все файлы (*)"
        )
        if not filepath:
            return
        # trusted=True — файл выбран пользователем, он попадает в белый список
        res = self._file_reader.read_file(filepath, trusted=True)
        if res.success:
            self._status_label.setText(f"Файл загружен: {Path(filepath).name}")
        else:
            self._status_label.setText(f"Ошибка: {res.error}")

    # ── Диалог ────────────────────────────────────────────────

    def _on_user_message(self, text: str):
        if self._is_streaming():
            # Ввод на это время заблокирован, но защищаемся и здесь:
            # второй поток параллельно первому не создаём.
            return
        if not self._llm.is_connected:
            self._chat.add_assistant_message(
                "⚠️ Сначала задай API ключ GPTunnel — нажми кнопку «🔑 API» в тулбаре."
            )
            return

        # Добавить в чат
        self._chat.add_user_message(text)

        # Сохранить в память (add_message возвращает индекс сообщения)
        self._memory.dialog.add_message("user", text)

        # Наблюдение о диалоге — пишется в файл наблюдений
        self._memory.observations.add(
            text[:300],
            context=f"Сессия: {self._memory.dialog.current_title or 'без названия'}",
        )

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

        self._start_stream(messages, self._on_stream_finished)

    def _process_skill_blocks(self):
        """Сохранить навыки из служебных блоков <skill> последнего ответа."""
        worker = self._stream_worker
        if worker is None or getattr(worker, "was_cancelled", False):
            return  # при отмене ответа навык из обрывка не создаём
        blocks = extract_skill_blocks(getattr(worker, "raw_text", ""))
        if not blocks:
            return
        saved: list[str] = []
        for block in blocks:
            try:
                write_skill(block["name"], block["description"], block["content"])
                saved.append(block["name"])
            except OSError as e:
                self._status_label.setText(
                    f"Не удалось сохранить навык {block['name']}: {e}"
                )
        if saved:
            self._skill_registry.reload()
            self._rebuild_skills_menu()
            self._status_label.setText("💾 Навык сохранён: " + ", ".join(saved))

    def _on_stream_finished(self):
        self._stream_active = False
        self._chat.finish_assistant_message()
        self._chat.set_enabled(True)
        self._status_label.setText("Готов к работе")

        # Сохранить ответ в память
        self._save_last_assistant_reply()

        # Предложить сохранить факты из последнего сообщения пользователя
        # (при закрытии окна диалоги не показываем)
        if not self._closing:
            session = self._memory.dialog.current_messages()
            for msg in reversed(session):
                if msg["role"] == "user":
                    facts = detect_facts(msg["content"], self._memory.facts)
                    for f in facts:
                        dlg = FactDialog(f["key"], f["label"], f["value"], self)
                        if dlg.exec() == QDialog.DialogCode.Accepted:
                            save_fact(f["key"], dlg.fact_value, self._memory.facts)
                            self._status_label.setText(f"Запомнил: {f['label']}")
                    break

        # Авто-создание навыков из служебных блоков <skill> ответа
        self._process_skill_blocks()

        self._memory.save_all()

    def _on_stream_error(self, error_msg: str):
        self._stream_active = False
        # Сохранить то, что успело напечататься, и отдельную запись об ошибке —
        # иначе у пользователя остаётся сообщение без ответа в истории.
        bubble = self._chat.last_message()
        if bubble is not None and bubble.role == "assistant":
            if bubble.text.strip():
                bubble.history_index = self._memory.dialog.add_message(
                    "assistant", bubble.text
                )
            else:
                # Пустой пузырь не сохраняем и убираем из UI, чтобы
                # история и чат оставались согласованными.
                self._chat.discard_last_message()
        self._chat.finish_assistant_message()

        err_bubble = self._chat.add_assistant_message(f"❌ {error_msg}")
        err_bubble.history_index = self._memory.dialog.add_message(
            "assistant", f"❌ {error_msg}"
        )
        self._chat.set_enabled(True)
        self._status_label.setText("Ошибка")
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

    def _on_regenerate_requested(self, bubble, new_text: str):
        """Заменить сообщение в диалоге и перегенерировать ответ.

        Сопоставление — по объекту пузыря и его индексу в истории,
        а не по тексту: текст пузыря к этому моменту уже обновлён.
        """
        if self._is_streaming():
            self._status_label.setText(
                "Дождись окончания ответа — потом правь сообщение"
            )
            return
        session = self._memory.dialog.current_messages()
        idx = bubble.history_index
        if idx is None or idx >= len(session) or session[idx]["role"] != "user":
            return

        # История: обновить текст и убрать старый ответ
        session[idx]["content"] = new_text
        removed = False
        if idx + 1 < len(session) and session[idx + 1]["role"] == "assistant":
            del session[idx + 1]
            removed = True

        # UI: текст пузыря уже обновлён, убираем пузырь старого ответа
        if removed:
            self._chat.remove_message_after(bubble)
            self._chat.shift_history_indices(from_index=idx + 1, delta=-1)

        self._memory.save_all()

        context_md = self._memory.get_full_context(user_query=new_text)
        files_content = self._file_reader.get_all_content()
        system_prompt = build_system_prompt(
            config=self._config,
            context_md=context_md,
            loaded_files_content=files_content,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._memory.dialog.get_messages_for_api(max_messages=30))

        self._start_stream(messages, self._on_stream_finished)

    # ── Сессии ────────────────────────────────────────────────

    def _on_new_session(self):
        if self._is_streaming():
            self._status_label.setText("Дождись окончания ответа — потом меняй сессию")
            return
        title, ok = QInputDialog.getText(self, "Новая сессия", "Название (можно оставить пустым):")
        if not ok:
            return
        self._memory.save_all()
        self._memory.new_session(title.strip(), self._config.model)
        self._memory.save_all()
        self._chat.clear_chat()
        self._refresh_sessions()
        self._memory.log_session_event(f"начата сессия «{title.strip() or 'без названия'}»")
        self._status_label.setText("Новая сессия начата")

    def _on_delete_session(self):
        if self._is_streaming():
            self._status_label.setText("Дождись окончания ответа — потом удаляй сессию")
            return
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
            deleted = self._memory.dialog.delete_session(session_id)
            self._chat.clear_chat()
            remaining = self._memory.dialog.list_sessions()
            if remaining:
                self._on_session_selected(remaining[0]["id"])
                if deleted:
                    self._status_label.setText(f"Сессия удалена, переключено на «{remaining[0]['title']}»")
                else:
                    self._status_label.setText("Файл сессии на диске не найден — память очищена")
            else:
                self._memory.new_session(model=self._config.model)
                self._refresh_sessions()
                self._status_label.setText(
                    "Все сессии удалены, создана новая" if deleted
                    else "Память очищена, создана новая сессия"
                )
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
        if self._is_streaming():
            # Иначе ответ старой сессии попадёт в историю новой
            self._status_label.setText("Дождись окончания ответа — потом переключай сессию")
            return
        self._generate_session_summary()
        self._memory.save_all()
        if self._memory.dialog.load_session(session_id):
            self._chat.clear_chat()
            history = self._memory.dialog.get_messages_for_api(max_messages=1000)
            if history:
                start_index = self._memory.dialog.history_start_index(len(history))
                self._chat.restore_from_history(history, start_index=start_index)
            title = self._memory.dialog.current_title or session_id
            self._session_btn.setText(title[:25])
            self._status_label.setText(f"Сессия: {title}")
            self._memory.log_session_event(f"включена сессия «{title}»")
            # Восстановить модель сессии: persist=False — сохранённая в config
            # глобальная модель при переключении не меняется.
            session_model = self._memory.dialog.get_session_model(session_id)
            if session_model and session_model != self._llm.model:
                self._llm.set_model(session_model)
                model_name = AgentConfig.get_model_name(session_model)
                self._model_btn.setText(model_name.split(" (")[0] if " (" in model_name else model_name)

    def _generate_session_summary(self):
        messages = self._memory.dialog.current_messages()
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

    # ── Закрытие ──────────────────────────────────────────────

    def _stop_background_threads(self):
        """Отменить и дождаться фоновые потоки (стриминг и список моделей).

        Без этого Qt уничтожает работающий QThread и приложение падает с
        «QThread: Destroyed while thread is still running».
        """
        if self._stream_worker is not None:
            self._stream_worker.cancel()
        for thread in (self._stream_thread, self._models_thread):
            if thread is None:
                continue
            if thread.isRunning() and not thread.wait(THREAD_WAIT_MS):
                # Поток завис в сетевом запросе — гасим принудительно,
                # иначе уничтожение работающего QThread приведёт к падению.
                thread.terminate()
                thread.wait(1000)
            thread.deleteLater()
        if self._stream_worker is not None:
            self._stream_worker.deleteLater()
        if self._models_worker is not None:
            self._models_worker.deleteLater()
        self._stream_thread = None
        self._stream_worker = None
        self._stream_active = False
        self._models_thread = None
        self._models_worker = None

    def closeEvent(self, event):
        self._closing = True
        self._stop_background_threads()
        self._memory.save_all()
        # Сохранить загруженные файлы в конфиг (абсолютные пути)
        self._config.loaded_files = list(self._file_reader.loaded_filenames)
        self._config.save()
        super().closeEvent(event)
