"""
Модальное окно выбора модели: поиск по списку.

Заменяет старые варианты (выпадающее меню и комбобокс). Один источник
данных — список моделей в формате list[dict]: id, name, provider.

Цены приложение НЕ считает и НЕ хранит: в окне стоит ссылка на
актуальный прайс GPTunnel — https://www.gptunnel.ru/ru/prices.

Стиль списка задаётся на самом QListWidget (собственный stylesheet):
глобальное правило app_stylesheet даёт QWidget светлый цвет текста, а фон
списка без своего правила остаётся системным светлым — текст выходил
невидимым до клика (рисовался только тёмный фон выделения).

Импорты плоские (соглашение проекта): модуль лежит в agent/gui/.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
)

from config import PALETTE

PRICES_URL = "https://www.gptunnel.ru/ru/prices"


class _ModelRowDelegate(QStyledItemDelegate):
    """Фон строки рисуется вручную, а не стилем.

    На Windows QSS-правила `::item:selected` и `selection-*` могли не
    сработать — пользователь видел белое выделение. Делегат рисует фон сам:
    цвет строки не зависит от движка, палитры и прозрачности.
    """

    def paint(self, painter, option, index):
        rect = option.rect
        # Сначала сплошная база строки: подложка на Windows может быть белой,
        # поэтому ни одного полупрозрачного слоя — только заливки без альфы.
        base = QColor(PALETTE["bg_light"] if index.row() % 2 else PALETTE["input_bg"])
        painter.fillRect(rect, base)
        state = option.state
        if state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor(PALETTE["accent_darker"]))  # тёмный бархатный фиолет
        elif state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor(46, 36, 60))                # #2e243c, сплошной

        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return
        lines = str(text).split("\n", 1)
        painter.save()
        painter.setPen(QColor(PALETTE["text_primary"]))  # один цвет текста в любом состоянии
        painter.setFont(option.font)
        align = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        painter.drawText(rect.adjusted(8, 3, -8, -(rect.height() // 2)), align, lines[0])
        if len(lines) > 1:
            painter.drawText(rect.adjusted(8, rect.height() // 2, -8, -3), align, lines[1])
        painter.restore()

    def sizeHint(self, option, _index):
        # две строки текста + внутренние отступы, как было в QSS (7px сверху/снизу)
        return QSize(option.rect.width(), option.fontMetrics.height() * 2 + 14)


class ModelSelectDialog(QDialog):
    """Выбор модели: строка поиска, список «модель / провайдер», ссылка на цены."""

    def __init__(self, models, current_id=None, subtitle=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Шелдон Павс — выбор модели")
        self.setMinimumSize(560, 480)
        self.selected_id: str | None = None
        self._models = list(models)

        p = PALETTE
        root = QVBoxLayout(self)
        root.setSpacing(10)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            root.addWidget(sub)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск: gpt, claude, 4o, gemini, mistral…")
        self._search.setClearButtonEnabled(True)
        root.addWidget(self._search)

        self._count = QLabel("")
        root.addWidget(self._count)

        self._list = QListWidget()
        self._list.setObjectName("model_list")
        self._list.setItemDelegate(_ModelRowDelegate(self._list))
        self._list.setMouseTracking(True)
        self._list.viewport().setMouseTracking(True)
        # фон под виджетом списка (в т.ч. отступы в 4px) — тоже вручную
        self._list.viewport().setStyleSheet(
            f"background-color: {p['input_bg']}; border: none;"
        )
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        # Выделение — непрозрачное и одинаковое для любой строки: полупрозрачный
        # фон (rgba) мог накладываться на светлую подложку и давать белый блик.
        # Дублируем свойством selection-* на самом виджете и палитрой — покрывает
        # и стили, и ветки, где QSS до элемента не доходит.
        self._list.setStyleSheet(f"""
            QListWidget#model_list {{
                background-color: {p['input_bg']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 4px;
                color: {p['text_primary']};
                font-size: 14px;
                selection-background-color: {p['accent_darker']};
                selection-color: {p['text_primary']};
            }}
            QListWidget#model_list::item {{
                padding: 7px 8px;
                border-radius: 4px;
                color: {p['text_primary']};
                background: transparent;
            }}
            QListWidget#model_list::item:alternate {{
                background: {p['bg_light']};
            }}
            QListWidget#model_list::item:hover {{
                background: #2e243c;
            }}
            QListWidget#model_list::item:selected,
            QListWidget#model_list::item:selected:!active {{
                background: {p['accent_darker']};
                color: {p['text_primary']};
            }}
        """)
        palette = self._list.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(p["accent_darker"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(p["text_primary"]))
        self._list.setPalette(palette)
        for m in self._models:
            name = str(m.get("name") or m.get("id") or "")
            pid = str(m.get("id") or "")
            provider = str(m.get("provider") or "")
            text = name if not provider else f"{name}\n{provider}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            # tooltip намеренно НЕ ставим: из-за stylesheet он превращается
            # в чёрный прямоугольник под курсором; id есть и в поиске
            self._list.addItem(item)
        root.addWidget(self._list, stretch=1)

        # Юридическое предупреждение: видно всегда, не прячется под скролл
        # (list — stretch=1, поэтому блок под ним фиксирован у низа).
        warn = QLabel(
            "Разработчиком моделей Muse и LLaMA является компания Meta, "
            "признанная в России экстремистской. Не нарушайте ФЗ РФ."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {p['warning']}; font-weight: bold;")
        root.addWidget(warn)

        link = QLabel(
            f'Цены — смотрите сами: <a href="{PRICES_URL}">gptunnel.ru/ru/prices</a>'
        )
        link.setOpenExternalLinks(True)
        link.setStyleSheet(f"color: {p['accent']};")
        root.addWidget(link)

        hint = QLabel("Enter или двойной клик — выбрать, Esc — отмена.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._select_btn = QPushButton("Выбрать")
        self._select_btn.setDefault(True)
        self._select_btn.setEnabled(False)
        cancel_btn = QPushButton("Отмена")
        buttons.addWidget(self._select_btn)
        buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

        self._search.textChanged.connect(self._apply_filter)
        self._search.returnPressed.connect(self._try_accept)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.itemDoubleClicked.connect(lambda _item: self.accept())
        self._select_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        self._preselect(current_id)
        self._apply_filter(self._search.text())
        self._search.setFocus()

    # ── Поведение ─────────────────────────────────────────────

    def _preselect(self, current_id) -> None:
        if not current_id:
            return
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == current_id:
                self._list.setCurrentRow(i)
                self._list.scrollToItem(self._list.item(i))
                return

    def _apply_filter(self, query: str) -> None:
        """Показать только подходящие под запрос строки; обновить счётчик."""
        q = query.strip().lower()
        visible = 0
        for i in range(self._list.count()):
            item = self._list.item(i)
            haystack = (
                item.text().lower() + " "
                + str(item.data(Qt.ItemDataRole.UserRole)).lower()
            )
            show = q in haystack if q else True
            item.setHidden(not show)
            if show:
                visible += 1
        self._count.setText(f"Найдено: {visible} из {self._list.count()}")

        # Автовыбор только когда под запросом ровно одна модель: Enter тогда
        # сразу её выбирает. При нескольких совпадениях ничего не выбираем
        # само собой — случайный Enter не должен менять модель.
        current = self._list.currentItem()
        if current is not None and current.isHidden():
            self._list.setCurrentRow(-1)
        if self._first_visible_row() >= 0 and visible == 1:
            self._list.setCurrentRow(self._first_visible_row())

    def _first_visible_row(self) -> int:
        for i in range(self._list.count()):
            if not self._list.item(i).isHidden():
                return i
        return -1

    def _on_current_changed(self, current, _previous) -> None:
        self._select_btn.setEnabled(current is not None and not current.isHidden())

    def _try_accept(self) -> None:
        """Enter: выбрать, если под запросом есть хотя бы одна строка."""
        row = self._list.currentRow()
        if row >= 0 and not self._list.item(row).isHidden():
            self.accept()

    def accept(self) -> None:
        item = self._list.currentItem()
        if item is None or item.isHidden():
            return  # без выбора закрываться нечем
        self.selected_id = item.data(Qt.ItemDataRole.UserRole)
        super().accept()
