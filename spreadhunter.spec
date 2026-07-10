# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Spreadhunter v0.1.0
# Criptografia via --key (bytecode encryption). Sem PyArmor.

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("config/parametros_default.json", "config"),
        ("config/spreadhunter_prioridade.json", "config"),
        ("temas/*", "temas"),
        ("src/ui/desktop/engine_perf.png", "src/ui/desktop"),
    ] + [
        (str(p), f"src/infrastructure/integrations/pnt_images/{p.name}")
        for p in __import__("pathlib").Path("src/infrastructure/integrations/pnt_images").iterdir()
        if p.suffix.lower() in (".png", ".md")
    ],
    hiddenimports=[
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "PySide6.QtXml", "PySide6.QtSvg",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "matplotlib", "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt5agg", "matplotlib.figure",
        "matplotlib.patches",
        "scipy", "scipy.stats", "scipy.optimize", "numpy",
        "requests", "bs4", "openpyxl", "dotenv",
        "pyautogui", "pygetwindow", "cv2", "psutil",
        "win32com", "win32api", "win32con", "win32gui",
        "win32process", "win32clipboard", "pythoncom",
        "hashlib", "logging.handlers", "sqlite3",
        "PIL", "PIL._tkinter_finder",
        "tzdata",
    ],
    excludes=[
        "tkinter", "pytest",
        "_distutils_hack", "setuptools", "pkg_resources",
        "cairo", "sphinx", "IPython", "zmq", "jedi", "parso",
        "matplotlib.tests", "scipy.tests",
        "mpl_toolkits", "pygments",
        "PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
    ],
    runtime_hooks=["scripts/runtime_hook.py"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name="Spreadhunter", debug=False, strip=False,
    upx=True, console=False, disable_windowed_traceback=False,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name="Spreadhunter", strip=False, upx=True, upx_exclude=[],
)
