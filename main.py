import logging
import os
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.infrastructure.persistence.bootstrap import bootstrap
from src.ui.desktop.main_window import MainWindow


def _configure_logging(db_path):
    """Configura logging conforme o parametro do sistema `diagnostico_logging`.

    Referencia principal: banco de parametros (diagnostico_logging, 0=off padrao).
    Env vars (SH_LOG_LEVEL, SH_PROFILE_MERCADO) funcionam apenas como override
    explicito e ruidoso (reportado no stderr) — nunca silencioso.
    """
    diag = False
    try:
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        p = ParametroRepository(db_path).get_by_chave("diagnostico_logging")
        if p is not None:
            diag = int(float(p.valor)) == 1
    except Exception:
        pass

    level = logging.DEBUG if diag else logging.INFO

    env_level = os.environ.get("SH_LOG_LEVEL")
    if env_level:
        try:
            level = int(getattr(logging, env_level.upper()))
            print(f"[logging] override env: SH_LOG_LEVEL={env_level} "
                  f"(param diagnostico_logging={int(diag)}) -> nivel {logging.getLevelName(level)}",
                  file=sys.stderr)
        except (AttributeError, ValueError):
            print(f"[logging] override env ignorado (invalido): SH_LOG_LEVEL={env_level}", file=sys.stderr)

    prof = diag
    env_prof = os.environ.get("SH_PROFILE_MERCADO")
    if env_prof is not None:
        prof = env_prof.strip() == "1"
        print(f"[logging] override env: SH_PROFILE_MERCADO={env_prof} "
              f"(param diagnostico_logging={int(diag)}) -> profile_mercado "
              f"{'ON' if prof else 'OFF'}", file=sys.stderr)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
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

    if not prof:
        return

    # Log de profiling para gargalos (sobrescrito a cada execucao).
    # Reproduzido apenas no modo diagnostico / override env.
    _prof_fmt = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                                  datefmt="%d/%m/%Y %H:%M:%S")
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
    _configure_logging(db_path)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(db_path)
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()