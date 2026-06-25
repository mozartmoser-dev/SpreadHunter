"""Monitor PETR4 — updates de 1 em 1 minuto"""
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

def le_f(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return float(v) if v else 0.0

def le_int(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return int(v) if v else 0

tick = 0
while True:
    rtd.refresh()
    spot = le_f("PETR4", RTD_CAMPO_ULTIMO_PRECO)
    bid_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_COMPRA)
    ask_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_VENDA)
    voc = le_int(COD_OTM, RTD_CAMPO_VOL_COMPRA)
    vov = le_int(COD_OTM, RTD_CAMPO_VOL_VENDA)

    minuto = time.strftime("%H:%M")
    segundo = int(time.time()) % 60
    if segundo % 12 == 0 or tick == 0:
        print(f"[{minuto}] Spot: R${spot:.2f} | OTM: {bid_o:.2f}/{ask_o:.2f} | VOC:{voc} VOV:{vov}")
        sys.stdout.flush()
    tick += 1
    time.sleep(3)
