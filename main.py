import logging
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication

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

logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

# Log de profiling para gargalos (sobrescrito a cada execução)
_prof_fmt = logging.Formatter("%(name)s | %(levelname)s | %(message)s")
_h1 = logging.FileHandler(Path("logs") / "profile_mercado.log", mode="w", encoding="utf-8")
_h1.setLevel(logging.DEBUG)
_h1.setFormatter(_prof_fmt)
logging.getLogger("src.infrastructure.providers.mercado_data_provider").addHandler(_h1)
logging.getLogger("src.infrastructure.providers.mercado_data_provider").setLevel(logging.DEBUG)

_h3 = logging.FileHandler(Path("logs") / "profile_mercado.log", mode="a", encoding="utf-8")
_h3.setLevel(logging.DEBUG)
_h3.setFormatter(_prof_fmt)
logging.getLogger("src.infrastructure.providers.openfast_socket_adapter").addHandler(_h3)
logging.getLogger("src.infrastructure.providers.openfast_socket_adapter").setLevel(logging.DEBUG)

_h2 = logging.FileHandler(Path("logs") / "profile_mercado.log", mode="a", encoding="utf-8")
_h2.setLevel(logging.DEBUG)
_h2.setFormatter(_prof_fmt)
class _FiltroManutencao(logging.Filter):
    def filter(self, record):
        return "Manutenção" in record.msg or "Ciclo:" in record.msg or "_flush_buffer" in record.msg or "Background scan" in record.msg or "Onda 1" in record.msg or "Lote Onda 1" in record.msg
_h2.addFilter(_FiltroManutencao())
logging.getLogger().addHandler(_h2)


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
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
