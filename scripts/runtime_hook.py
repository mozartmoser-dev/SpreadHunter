"""Runtime hook — PyInstaller."""
import os, sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "module://matplotlib.backends.backend_qtagg")

_base = Path(getattr(sys, "_MEIPASS", Path(sys.argv[0]).parent))
if str(_base) not in sys.path:
    sys.path.insert(0, str(_base))

# Cria diretório de logs no mesmo diretório do .exe (main.py usa path relativo)
(Path(sys.argv[0]).parent / "logs").mkdir(exist_ok=True)

try:
    import pywin32
    dll_dir = Path(pywin32.__file__).parent / "pywin32_system32"
    if dll_dir.is_dir():
        os.add_dll_directory(str(dll_dir))
except Exception:
    pass
