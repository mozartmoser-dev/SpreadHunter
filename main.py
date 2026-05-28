import logging
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from src.infrastructure.persistence.bootstrap import bootstrap
from src.ui.desktop.main_window import MainWindow

logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s | %(levelname)s | %(message)s",
    handlers=[
        RotatingFileHandler(
            Path("logs") / "spreadhunter.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)


def _clear_pycache():
    for pycache in Path(".").rglob("__pycache__"):
        try:
            shutil.rmtree(pycache)
        except Exception:
            pass


def run_app(db_path=None):
    _clear_pycache()
    bootstrap(db_path)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(db_path)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    run_app()
