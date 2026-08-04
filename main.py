"""
Агент Шелдон Павс — точка входа.
"""

import sys
import os

# Плоские импорты: модули лежат в agent/ (dev) или плоско в корне bundle (frozen).
if getattr(sys, "frozen", False):
    # PyInstaller кладёт agent/*.py на верхний уровень sys._MEIPASS
    _agent_dir = sys._MEIPASS
else:
    _agent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent")
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
