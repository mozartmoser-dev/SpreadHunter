"""Monitor PETR4 — análise a cada 2 min com projecoes"""
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

COD_ATM = "PETRT407"
COD_OTM = "PETRT394"
CAMPOS = [RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA,
          RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA]

for cod in ["PETR4", COD_ATM, COD_OTM]:
    rtd.registrar_status(cod)
    for campo in CAMPOS:
        rtd.registrar_topico(cod, campo)

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

spot_min = 100
spot_max = 0
start = time.time()
ciclo = 0

while True:
    rtd.refresh()
    spot = le_f("PETR4", RTD_CAMPO_ULTIMO_PRECO)
    if spot < spot_min and spot > 1: spot_min = spot
    if spot > spot_max: spot_max = spot
    
    bid_a = le_f(COD_ATM, RTD_CAMPO_OFERTA_COMPRA)
    ask_a = le_f(COD_ATM, RTD_CAMPO_OFERTA_VENDA)
    bid_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_COMPRA)
    ask_o = le_f(COD_OTM, RTD_CAMPO_OFERTA_VENDA)
    voc_o = le_int(COD_OTM, RTD_CAMPO_VOL_COMPRA)
    vov_o = le_int(COD_OTM, RTD_CAMPO_VOL_VENDA)
    cab_o = le_int(COD_OTM, RTD_CAMPO_CABECALHO_BOOK)
    
    agora = time.strftime("%H:%M:%S")
    decorrido = int(time.time() - start)
    
    print(f"\n{'='*55}")
    print(f"[{agora}] CICLO +{decorrido}s")
    print(f"{'='*55}")
    print(f"PETR4 SPOT: R${spot:.2f}  (dia: {spot_min:.2f} / {spot_max:.2f})")
    
    # Direcao curto prazo (ultimos 30 seg)
    dir_tendencia = ""
    if ciclo > 0:
        if spot > spot_prev + 0.02: dir_tendencia = "SUBINDO [+]"
        elif spot < spot_prev - 0.02: dir_tendencia = "CAINDO [-]"
        else: dir_tendencia = "LATERAL [=]"
        print(f"Direcao (2min): {dir_tendencia}")
    
    # Analise de niveis
    if spot <= 39.46:
        print(f"NIVEL: Abaixo do fundo anterior (39.46) — testando novo suporte")
        prox_suporte = "39.20-30 (Bollinger banda inf)"
    elif spot <= 39.52:
        print(f"NIVEL: Testando suporte 39.46-52 — zona de decisao")
        prox_suporte = "39.46 (fundo anterior)"
    elif spot <= 39.66:
        print(f"NIVEL: Entre 39.52 e Fibo 50% (39.66) — recuperacao fragil")
        prox_suporte = "39.52"
    elif spot <= 39.76:
        print(f"NIVEL: Entre Fibo 50% e S3 pivot — recuperacao moderada")
        prox_suporte = "39.66 (Fibo 50%)"
    else:
        print(f"NIVEL: Acima de 39.76 — recuperacao forte em curso")
        prox_suporte = "39.76 (S3 pivot)"
    
    # Projecao
    if dir_tendencia == "CAINDO [-]":
        print(f"PROJECAO: testando {prox_suporte} nas proximas barras")
        if ask_o >= 1.15:
            print(f"   Se cair: OTM ask pode ir a R$1.18-20")
    elif dir_tendencia == "SUBINDO [+]":
        prox_res = "39.66" if spot < 39.66 else "39.76" if spot < 39.76 else "40.47"
        print(f"PROJECAO: buscando R${prox_res} nas proximas barras")
        print(f"   Se subir: OTM ask pode cair para R$1.12-14")
    else:
        print(f"PROJECAO: indefinida — aguardar rompimento de 39.46 ou 39.66")
    
    # Credito estimado
    if ask_o > 0 and bid_a > 0:
        cred_cons = 2 * bid_o - ask_a
        cred_agr = 2 * ask_o - bid_a
        print(f"SPREAD: credito conservador R${cred_cons:.2f} | agressivo R${cred_agr:.2f}")
    
    print(f"BOOK OTM: {bid_o:.2f}/{ask_o:.2f} | VOC={voc_o} VOV={vov_o} | CAB={cab_o}")
    print(f"BOOK ATM: {bid_a:.2f}/{ask_a:.2f}")
    
    spot_prev = spot
    ciclo += 1
    sys.stdout.flush()
    
    # Espera 2 minutos
    for _ in range(24):
        time.sleep(5)
        rtd.refresh()
