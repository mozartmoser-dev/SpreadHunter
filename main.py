import logging
import sys

from PyQt5.QtWidgets import QApplication

from src.infrastructure.persistence.bootstrap import bootstrap
from src.ui.desktop.main_window import MainWindow

logging.basicConfig(level=logging.DEBUG, format="%(name)s | %(levelname)s | %(message)s")


def run_app(db_path=None):
    bootstrap(db_path)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(db_path)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    run_app()
