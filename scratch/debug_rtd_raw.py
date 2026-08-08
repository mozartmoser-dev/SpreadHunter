"""Debug descartavel — imprime os valores crus de cada padrao de topico srv.rtd."""
from __future__ import annotations

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

import pythoncom
import win32com.client

PROGID = "srv.rtd"
FIELDS = ["PEX", "LAST", "BID", "ASK"]
CODES = ["PETR4", "VALE3", "ITUB4"]
PATTERNS = [
    ("codigo", lambda c: c),
    ("codigo_B_0", lambda c: f"{c}_B_0"),
    ("codigo_B", lambda c: f"{c}_B"),
]

pythoncom.CoInitialize()
try:
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False
    excel.UserControl = False
    print(f"HWND={excel.Hwnd}")
except Exception as e:
    print(f"Falha ao abrir: {e}")
    raise

try:
    wb = excel.Workbooks.Add()
    ws = wb.Worksheets(1)
    for pos, (nome, fn) in enumerate(PATTERNS):
        ini = 2 + pos * (len(CODES) + 2)
        formulas = []
        for c in CODES:
            topico = fn(c)
            formulas.append(
                [f"=RTD(\"{PROGID}\",,\"{topico}\",\"{f}\")" for f in FIELDS]
            )
        rng = ws.Range(ws.Cells(ini, 1), ws.Cells(ini + len(CODES) - 1, len(FIELDS)))
        try:
            rng.Formula = formulas
        except Exception as e:
            print(f"[{nome}] erro ao gravar: {e}")
        time.sleep(3.0)
        raw = rng.Value
        print(f"\n### padrao [{nome}] ###")
        # converte Variant -> quando 1 linha vem como lista simples
        linhas = raw if isinstance(raw, (list, tuple)) else [raw]
        for i, linha in enumerate(linhas):
            if isinstance(linha, (list, tuple)):
                print(f"  {CODES[i]}: {[repr(x) for x in linha]}")
            else:
                print(f"  {CODES[i]}: {repr(linha)}")
        excel.Calculate()
        time.sleep(1.0)
        print("  (apos Calculate):")
        raw2 = rng.Value
        linhas2 = raw2 if isinstance(raw2, (list, tuple)) else [raw2]
        for i, linha in enumerate(linhas2):
            if isinstance(linha, (list, tuple)):
                print(f"  {CODES[i]}: {[repr(x) for x in linha]}")
            else:
                print(f"  {CODES[i]}: {repr(linha)}")
finally:
    try:
        wb.Close(SaveChanges=False)
    except Exception:
        pass
    try:
        excel.Quit()
    except Exception:
        pass
    pythoncom.CoUninitialize()

print("\nDEBUG_FIM")