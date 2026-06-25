"""Monitor bounce PETR4 — analise a cada 30 segundos"""
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

for cod in ["PETR4", COD_OTM]:
    rtd.registrar_status(cod)
    for campo in CAMPOS:
        rtd.registrar_topico(cod, campo)

rtd.refresh()
time.sleep(0.3)
rtd.refresh()

def le_f(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return float(v) if v else 0.0

def le_int(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return int(v) if v else 0

spot_low = 100
prev = 0
ciclo = 0

while True:
    rtd.refresh()
    spot = le_f("PETR4", RTD_CAMPO_ULTIMO_PRECO)
    bid_s = le_f("PETR4", RTD_CAMPO_OFERTA_COMPRA)
    ask_s = le_f("PETR4", RTD_CAMPO_OFERTA_VENDA)
    bid_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_COMPRA)
    ask_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_VENDA)
    voc_o = le_int(COD_OTM, RTD_CAMPO_VOL_COMPRA)
    vov_o = le_int(COD_OTM, RTD_CAMPO_VOL_VENDA)
    
    if spot < spot_low: spot_low = spot
    agora = time.strftime("%H:%M:%S")
    
    # Sinal de bounce?
    sinal = "AGUARDANDO"
    if prev > 0 and spot > prev + 0.03: sinal = "POSSIVEL BOUNCE (+) (+%.2f)" % (spot - prev)
    elif prev > 0 and spot < prev - 0.03: sinal = "CAINDO (-) (-%.2f)" % (prev - spot)
    elif ciclo > 0 and spot >= spot_low + 0.08: sinal = "BOUNCE CONFIRMADO +%.2f DO FUNDO" % (spot - spot_low)
    
    # Analise
    analise = "nada"
    if spot < 39.20: analise = "ABAIXO 39.20 — extracao!"
    elif spot < 39.30: analise = "39.20-30 — zona de decisao"
    elif spot < 39.40: analise = "39.30-40 — recuperando"
    elif spot < 39.50: analise = "39.40-50 — tendencia neutra"
    else: analise = "ACIMA 39.50 — recuperacao forte"
    
    print(f"[{agora}] Spot R${spot:.2f} (low: {spot_low:.2f}) | OTM {bid_o:.2f}/{ask_o:.2f} V:{voc_o}/{vov_o} | {sinal}")
    if ciclo % 2 == 0:
        print(f"  >> {analise}")
        if ask_o >= 1.25: print(f"  >> R$1.25 no ask — ordem pode pegar!")
        elif ask_o < 1.25: print(f"  >> Ask OTM = R${ask_o:.2f} — R$1.25 esta +{(1.25-ask_o):.2f} acima")
    
    sys.stdout.flush()
    prev = spot
    ciclo += 1
    time.sleep(7)
