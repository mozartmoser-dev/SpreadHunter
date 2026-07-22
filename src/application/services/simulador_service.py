import json
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

SIMULADOR_SCRIPT = "scripts/simulador_gregas.py"
CENARIO_JSON = "cenario_atual.json"


def exportar_para_simulador(dados_operacao: dict) -> None:
    root = Path(__file__).resolve().parent.parent.parent.parent

    json_path = root / CENARIO_JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados_operacao, f, indent=4)

    script_path = root / SIMULADOR_SCRIPT
    if not script_path.exists():
        logger.error("Simulador nao encontrado: %s", script_path)
        return

    try:
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(script_path)],
            cwd=str(root),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as e:
        logger.error("Falha ao iniciar Streamlit: %s", e)
        return

    webbrowser.open("http://localhost:8501")
