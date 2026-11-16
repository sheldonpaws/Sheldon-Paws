"""
Стили GUI — палитра «FangUnion» (тёмная фиолетовая тема).
"""

from config import PALETTE


def app_stylesheet() -> str:
    """Главная таблица стилей приложения."""
    p = PALETTE
    return f"""
    /* === Глобальные === */
    QMainWindow {{
        background-color: {p['bg_main']};
    }}
    QWidget {{
        font-family: 'Georgia', 'Segoe UI', serif;
        font-size: 14px;
        color: {p['text_primary']};
    }}

    /* === Чат === */
    #chat_area QScrollBar:vertical {{
        background: {p['bg_main']};
        width: 8px;
        border-radius: 4px;
    }}
    #chat_area QScrollBar::handle:vertical {{
        background: {p['scrollbar']};
        min-height: 30px;
        border-radius: 4px;
    }}
    #chat_area QScrollBar::add-line:vertical,
    #chat_area QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* === Сообщения === */
    #user_message {{
        background: transparent;
        border: none;
        padding: 6px 8px;
        margin: 2px 8px 2px 8px;
    }}
    #assistant_message {{
        background: transparent;
        border: none;
        padding: 6px 8px;
        margin: 2px 8px 2px 8px;
    }}
    #message_label {{
        font-size: 15px;
        line-height: 1.6;
        color: {p['text_primary']};
    }}
    #sender_label {{
        font-size: 11px;
        font-weight: bold;
        color: {p['gold']};
        margin-bottom: 2px;
    }}

    /* === Поле ввода === */
    #input_field {{
        background-color: {p['input_bg']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 14px;
        min-height: 44px;
        max-height: 120px;
        color: {p['text_primary']};
    }}
    #input_field:focus {{
        border-color: {p['accent']};
    }}

    /* === Кнопки === */
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {p['accent_dark']}, stop:1 {p['accent_darker']});
        color: {p['text_primary']};
        border: 1px solid {p['accent']};
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: bold;
        min-height: 36px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {p['accent']}, stop:1 {p['accent_dark']});
    }}
    QPushButton:pressed {{
        background-color: {p['accent_darker']};
    }}
    QPushButton:disabled {{
        background-color: {p['border']};
        color: {p['text_secondary']};
    }}
    #secondary_button {{
        background-color: transparent;
        color: {p['accent']};
        border: 1px solid {p['accent']};
    }}
    #secondary_button:hover {{
        background-color: {p['bg_light']};
    }}
    #danger_button {{
        background-color: {p['warning']};
    }}
    #danger_button:hover {{
        background-color: #a04040;
    }}

    /* === Тулбар === */
    QToolBar {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p['toolbar']}, stop:1 {p['toolbar_dark']});
        border-bottom: 2px solid {p['accent_dark']};
        spacing: 4px;
        padding: 2px;
    }}
    QToolButton {{
        color: {p['text_primary']};
        background: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 6px 12px;
        font-weight: bold;
    }}
    QToolButton:hover {{
        background: rgba(148, 120, 182, 0.15);
        border-color: {p['accent']};
    }}
    QToolButton::menu-indicator {{
        image: none;
        width: 0px;
    }}

    /* === Меню (выпадающие списки) === */
    QMenu {{
        background-color: {p['bg_light']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 16px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: rgba(148, 120, 182, 0.2);
        color: {p['gold']};
    }}
    QMenu::item:disabled {{
        color: {p['text_secondary']};
    }}

    /* === Комбобокс === */
    QComboBox {{
        background-color: {p['input_bg']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        padding: 6px 12px;
        min-height: 30px;
        color: {p['text_primary']};
    }}
    QComboBox:focus {{
        border-color: {p['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p['bg_light']};
        border: 1px solid {p['border']};
        selection-background-color: rgba(148, 120, 182, 0.2);
        selection-color: {p['gold']};
    }}

    /* === Чекбоксы (навыки) === */
    QCheckBox {{
        spacing: 8px;
        color: {p['text_primary']};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid {p['border']};
        background-color: {p['bg_main']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {p['accent']};
        border-color: {p['accent']};
    }}

    /* === Список файлов === */
    #file_list {{
        background-color: {p['input_bg']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        padding: 4px;
    }}
    #file_list QScrollBar:vertical {{
        background: {p['input_bg']};
        width: 8px;
    }}
    #file_list QScrollBar::handle:vertical {{
        background: {p['scrollbar']};
        min-height: 20px;
        border-radius: 4px;
    }}

    /* === Статус-бар === */
    QStatusBar {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p['toolbar_dark']}, stop:1 {p['toolbar']});
        color: {p['text_primary']};
        font-size: 12px;
        padding: 2px 12px;
        border-top: 1px solid {p['border']};
    }}

    /* === Диалоги === */
    QDialog {{
        background-color: {p['bg_main']};
    }}
    QLineEdit {{
        background-color: {p['input_bg']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 30px;
        color: {p['text_primary']};
    }}
    QLineEdit:focus {{
        border-color: {p['accent']};
    }}

    /* === Сплиттер === */
    QSplitter::handle {{
        background-color: {p['border']};
        width: 2px;
    }}

    /* === Scroll Area === */
    QScrollArea {{
        border: none;
    }}

    /* === Скроллбар глобальный === */
    QScrollBar:vertical {{
        background: {p['bg_main']};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['scrollbar']};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p['accent']};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """

