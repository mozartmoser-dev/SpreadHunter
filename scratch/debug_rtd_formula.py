"""Debug — confere o que a celula realmente contem (Formula/Value/Text) e testa 2 sintaxes RTD."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

import pythoncom
import win32com.client

PROGID = "srv.rtd"

pythoncom.CoInitialize()
excel = None
wb = None
try:
    excel = win32com.client.DispatchEx("Excel.Application")
    xl = excel
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.ScreenUpdating = False
    xl.EnableEvents = True
    xl.UserControl = False
    print(f"HWND={xl.Hwnd}")
    wb = xl.Workbooks.Add()
    ws = wb.Worksheets(1)

    # col A: sintaxe padrão; col B: com server "" explicito; col C: topic minusculo
    celulas = {
        "A2": '=RTD("srv.rtd",,"PETR4","PEX")',
        "B2": '=RTD("srv.rtd","","PETR4","PEX")',
        "C2": '=RTD("srv.rtd",,"petr4","PEX")',
        "D2": '=RTD("srv.rtd",,"PETR4_B_0","PEX")',
        "E2": '=RTD("srv.rtd",,"PETR4","BID")',
        "F2": '=RTD("srv.rtd",,"PETR4","ST")',
    }
    for addr, f in celulas.items():
        try:
            ws.Range(addr).Formula = f
            print(f"gravado {addr} -> {f}")
        except Exception as e:
            print(f"ERRO gravacao {addr}: {e}")

    for espera in (2.0, 5.0):
        time.sleep(espera)
        print(f"\n--- apos {espera:.0f}s ---")
        for addr in celulas:
            try:
                formula = ws.Range(addr).Formula
            except Exception:
                formula = "?"
            try:
                val = ws.Range(addr).Value
            except Exception:
                val = "?"
            try:
                txt = ws.Range(addr).Text
            except Exception:
                txt = "?"
            print(f"  {addr}: Formula={formula!r} Value={val!r} Text={txt!r}")

    # comando calcular forçado
    try:
        xl.Calculate()
        time.sleep(3.0)
        print("\n--- apos Calculate ---")
        for addr in celulas:
            try:
                print(f"  {addr}: Value={ws.Range(addr).Value!r} Text={ws.Range(addr).Text!r}")
            except Exception:
                pass
    except Exception as e:
        print(f"calculate falhou: {e}")
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