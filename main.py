from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from ui.main_window import create_main_window
from utils.logger import setup_logging


def main() -> int:
    setup_logging()

    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent.joinpath("res", "logo.png")
    app.setWindowIcon(QIcon(str(icon_path)))
    jar_path = str(Path(__file__).resolve().parent.joinpath("jar", "plantuml.jar"))
    win = create_main_window(jar_path)
    win.setWindowIcon(QIcon(str(icon_path)))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
