"""Monitor PETR4 a cada 20s — divergencias + bounce"""
import pythoncom
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.rtd_config import (
    RTD_CAMPO_ULTIMO_PRECO as ULT, RTD_CAMPO_OFERTA_COMPRA as OCP,
    RTD_CAMPO_OFERTA_VENDA as OVD, RTD_CAMPO_CABECALHO_BOOK as CAB,
    RTD_CAMPO_VOL_COMPRA as VOC, RTD_CAMPO_VOL_VENDA as VOV,
    RTD_CAMPO_STATUS as EST, RTD_CAMPO_STRIKE as PEX,
)
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
rtd = RTDProfit()
for cod in ["PETR4", "PETRT394"]:
    rtd.registrar_status(cod)
    for c in [ULT, OCP, OVD, CAB, VOC, VOV]:
        rtd.registrar_topico(cod, c)
rtd.refresh(); time.sleep(0.3); rtd.refresh()

def lef(c, f):
    v = rtd.ler_campo_cache(c, f)
    return float(v) if v else 0.0

def lei(c, f):
    v = rtd.ler_campo_cache(c, f)
    return int(v) if v else 0

low = 100
prev_spot = 0
prev_vov = 0
vol_direcao = ""
spot_direcao = ""
divergencia = ""
ciclo = 0

while True:
    rtd.refresh()
    spot = lef("PETR4", ULT)
    bid_s = lef("PETR4", OCP)
    ask_s = lef("PETR4", OVD)
    bid_o = lef("PETRT394", OCP)
    ask_o = lef("PETRT394", OVD)
    voc = lei("PETRT394", VOC)
    vov = lei("PETRT394", VOV)

    if spot < low and spot > 1: low = spot
    agora = time.strftime("%H:%M:%S")
    
    # Direcoes
    if prev_spot > 0:
        if spot > prev_spot + 0.02: spot_direcao = "SUBINDO"
        elif spot < prev_spot - 0.02: spot_direcao = "CAINDO"
        else: spot_direcao = "LATERAL"
    if prev_vov > 0:
        if vov > prev_vov * 1.3: vol_direcao = "AUMENTANDO"
        elif vov < prev_vov * 0.7: vol_direcao = "DIMINUINDO"
        else: vol_direcao = "ESTAVEL"
    
    # Divergencia
    if "CAINDO" in spot_direcao and "DIMINUINDO" in vol_direcao:
        divergencia = "[DIVERGENCIA BAIXA] preco cai, oferta cai = exaustao"
    elif "LATERAL" in spot_direcao and "DIMINUINDO" in vol_direcao:
        divergencia = "[SINAl] estabilizando com menos oferta"
    elif "CAINDO" in spot_direcao and "AUMENTANDO" in vol_direcao:
        divergencia = "[FORCA BAIXISTA] mais oferta surgindo"
    elif "SUBINDO" in spot_direcao and "AUMENTANDO" in vol_direcao:
        divergencia = "[SINAl] recuperando com oferta crescendo"
    else:
        divergencia = ""
    
    # Linha
    saida = f"[{agora}] SPT={spot:.2f} BID={bid_s:.2f} ASK={ask_s:.2f} | OTM={bid_o:.2f}/{ask_o:.2f} V={voc}/{vov}"
    saida += f" | spot={spot_direcao} vol={vol_direcao}"
    if divergencia:
        saida += f" | {divergencia}"
    
    print(saida)
    sys.stdout.flush()
    
    prev_spot = spot
    prev_vov = vov
    ciclo += 1
    time.sleep(10)
