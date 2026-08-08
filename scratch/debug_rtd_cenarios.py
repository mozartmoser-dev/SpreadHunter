"""Debug â€” compara Empty vs dados em 4 cenarios: VisibleOn/Off x EventsOn/Off."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

import pythoncom
import win32com.client

PROGID = "srv.rtd"
FIELDS = ["PEX", "LAST", "BID", "ASK"]

def _ler(ws, ini, codes):
    rng = ws.Range(ws.Cells(ini, 1), ws.Cells(ini + len(codes) - 1, len(FIELDS)))
    try:
        raw = rng.Value
    except Exception as e:
        return f"erro ler: {e}"
    linhas = raw if isinstance(raw, (list, tuple)) else [raw]
    out = []
    for i, linha in enumerate(linhas):
        if isinstance(linha, (list, tuple)):
            out.append((codes[i], [repr(x) for x in linha]))
        else:
            out.append((codes[i], repr(linha)))
    return out

def escrever(ws, ini, codes, topico_fn):
    formulas = [
        [f"=RTD(\"{PROGID}\",,\"{topico_fn(c)}\",\"{f}\")" for f in FIELDS]
        for c in codes
    ]
    rng = ws.Range(ws.Cells(ini, 1), ws.Cells(ini + len(codes) - 1, len(FIELDS)))
    try:
        rng.Formula = formulas
        return "ok"
    except Exception as e:
        return f"erro formula: {e}"

CODES = ["PETR4", "VALE3", "ITUB4"]

pythoncom.CoInitialize()
excel = None
wb = None
try:
    excel = win32com.client.DispatchEx("Excel.Application")
    xl = excel
    xl.DisplayAlerts = False
    xl.ScreenUpdating = False
    xl.Visible = True  # vamos alternar manualmente em cada cenario
    xl.UserControl = False
    print(f"HWND={xl.Hwnd}")
    wb = xl.Workbooks.Add()
    ws = wb.Worksheets(1)

    cenarios = [
        ("visible=True eventsOn",  True,  True),
        ("visible=True eventsOFF", True,  False),
        ("visible=False eventsOn", False, True),
        ("visible=False eventsOFF",False, False),
    ]
    ini = 2
    for nome, vis, ev in cenarios:
        xl.Visible = vis
        try:
            xl.EnableEvents = ev
        except Exception:
            pass
        topico = lambda c: c
        status = escrever(ws, ini, CODES, topico)
        print(f"\n### {nome} | gravar={status} ###")
        time.sleep(4.0)
        for rotulo, dados in (("4s", _ler(ws, ini, CODES)),):
            for cod, linha in dados:
                print(f"  {cod}: {linha}")
        # tenta forcar calculo
        try:
            xl.Calculate()
        except Exception:
            pass
        time.sleep(1.0)
        print("  (apos Calculate)")
        for cod, linha in _ler(ws, ini, CODES):
            print(f"  {cod}: {linha}")
        ini += len(CODES) + 2
finally:
    try:
        excel.Quit()
    except Exception:
        pass
    try:
        wb.Close(SaveChanges=False)
    except Exception:
        pass
    pythoncom.CoUninitialize()

print("\nDEBUG_FIM")
