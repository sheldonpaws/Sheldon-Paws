"""
Агент Шелдон Павс — точка входа.
"""

import sys
import os

# Добавить директорию agent/ в путь для импортов
_agent_dir = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # PyInstaller: агент лежит внутри bundle
    _agent_dir = os.path.join(sys._MEIPASS, "agent")
sys.path.insert(0, _agent_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from gui.main_window import MainWindow


def main():
    # High DPI поддержка
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Шелдон Павс — Агент")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
