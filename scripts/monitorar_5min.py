"""Monitora PETR4 spot + OTM 38.36 por 5 min"""
import pythoncom
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.rtd_config import (
    RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA,
    RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA,
)
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
rtd = RTDProfit()

COD_OTM = "PETRT394"
CAMPOS = [RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA,
          RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA]

rtd.registrar_status("PETR4")
for campo in CAMPOS:
    rtd.registrar_topico("PETR4", campo)
    rtd.registrar_topico(COD_OTM, campo)

rtd.refresh()
time.sleep(0.3)
rtd.refresh()
time.sleep(0.3)

print(f"{'HORA':<10} {'SPOT':<8} {'BID_SPOT':<9} {'ASK_SPOT':<9} {'BID_OTM':<8} {'ASK_OTM':<8} {'VOC':<6} {'VOV':<6} {'CAB':<5}")
print(f"{'-'*70}")

def le_f(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return float(v) if v else 0.0

def le_int(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return int(v) if v else 0

start = time.time()
while time.time() - start < 330:
    mudou = rtd.refresh()
    if not mudou and time.time() - start > 10:
        if int(time.time() - start) % 10 != 0:
            time.sleep(3)
            continue
    t = time.strftime("%H:%M:%S")
    spot = le_f("PETR4", RTD_CAMPO_ULTIMO_PRECO)
    bid_s = le_f("PETR4", RTD_CAMPO_OFERTA_COMPRA)
    ask_s = le_f("PETR4", RTD_CAMPO_OFERTA_VENDA)
    bid_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_COMPRA)
    ask_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_VENDA)
    voc = le_int(COD_OTM, RTD_CAMPO_VOL_COMPRA)
    vov = le_int(COD_OTM, RTD_CAMPO_VOL_VENDA)
    cab = le_int(COD_OTM, RTD_CAMPO_CABECALHO_BOOK)
    print(f"{t:<10} {spot:<8.2f} {bid_s:<9.2f} {ask_s:<9.2f} {bid_o:<8.2f} {ask_o:<8.2f} {voc:<6} {vov:<6} {cab:<5}")
    time.sleep(5)

rtd.desconectar()
pythoncom.CoUninitialize()
