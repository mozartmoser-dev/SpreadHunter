"""Script para ler PETR4 do Profit RTD e calcular Put Ratio Spread."""
import pythoncom
import sys
import time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.rtd_config import (
    RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA,
    RTD_CAMPO_STRIKE, RTD_CAMPO_VENCIMENTO, RTD_CAMPO_CABECALHO_BOOK,
    RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA, RTD_CAMPO_STATUS,
)

import os
os.environ["PYTHONIOENCODING"] = "utf-8"

pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
rtd = RTDProfit()
if not rtd.disponivel:
    print("\nERRO: Profit RTD nao disponivel. Profit esta aberto?")
    pythoncom.CoUninitialize()
    sys.exit(1)

print("\nConectado ao Profit RTD!")

PETR4 = "PETR4"
CODS = [
    "PETRT407",
    "PETRT394",
    "PETRT382",
]

CAMPOS = [RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA,
          RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_CABECALHO_BOOK,
          RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA,
          RTD_CAMPO_STRIKE, RTD_CAMPO_VENCIMENTO]

print("Registrando topicos...")
rtd.registrar_status(PETR4)
rtd.registrar_topico(PETR4, RTD_CAMPO_ULTIMO_PRECO)
rtd.registrar_topico(PETR4, RTD_CAMPO_OFERTA_COMPRA)
rtd.registrar_topico(PETR4, RTD_CAMPO_OFERTA_VENDA)

for cod in CODS:
    for campo in CAMPOS:
        rtd.registrar_topico(cod, campo)
    rtd.registrar_status(cod)

print("Fazendo refresh (2x)...")
rtd.refresh()
time.sleep(0.3)
rtd.refresh()
time.sleep(0.3)
rtd.refresh()

def le_f(codigo, campo):
    v = rtd.ler_campo_cache(codigo, campo)
    if v is None: return None
    return float(v)

def le_s(codigo):
    return rtd.ler_status_cache(codigo) or "-"

spot_bid = le_f(PETR4, RTD_CAMPO_OFERTA_COMPRA)
spot_ask = le_f(PETR4, RTD_CAMPO_OFERTA_VENDA)
spot_ult = le_f(PETR4, RTD_CAMPO_ULTIMO_PRECO)

print(f"\n{'='*60}")
print(f"PETR4 SPOT")
print(f"  ULTIMO: {spot_ult:.2f}" if spot_ult else "  ULTIMO: -")
print(f"  BID:    {spot_bid:.2f}" if spot_bid else "  BID:    -")
print(f"  ASK:    {spot_ask:.2f}" if spot_ask else "  ASK:    -")
print(f"  STATUS: {le_s(PETR4)}")

print(f"\n{'='*60}")
print(f"{'COD':<12} {'STRIKE':<8} {'BID':<8} {'ASK':<8} {'CAB':<6} {'VOC':<6} {'VOV':<6}")
print(f"{'-'*60}")

results = {}
for cod in CODS:
    strike = le_f(cod, RTD_CAMPO_STRIKE)
    bid = le_f(cod, RTD_CAMPO_OFERTA_COMPRA)
    ask = le_f(cod, RTD_CAMPO_OFERTA_VENDA)
    cab = le_f(cod, RTD_CAMPO_CABECALHO_BOOK)
    voc = le_f(cod, RTD_CAMPO_VOL_COMPRA)
    vov = le_f(cod, RTD_CAMPO_VOL_VENDA)
    status = le_s(cod)

    s_s = f"{strike:.2f}" if strike else "-"
    b_s = f"{bid:.2f}" if bid else "-"
    a_s = f"{ask:.2f}" if ask else "-"
    cab_s = f"{int(cab)}" if cab else "-"
    voc_s = f"{int(voc)}" if voc else "-"
    vov_s = f"{int(vov)}" if vov else "-"

    print(f"{cod:<12} {s_s:<8} {b_s:<8} {a_s:<8} {cab_s:<6} {voc_s:<6} {vov_s:<6}  [{status}]")

    results[cod] = {"bid": bid, "ask": ask, "strike": strike, "cab": cab, "voc": voc, "vov": vov}

print(f"\n{'='*60}")
print("PUT RATIO SPREAD 1:2")
print(f"{'-'*60}")

atm = "PETRT407"
otm = "PETRT394"

atm_bid = results.get(atm, {}).get("bid")
atm_ask = results.get(atm, {}).get("ask")
otm_bid = results.get(otm, {}).get("bid")
otm_ask = results.get(otm, {}).get("ask")

strike_atm = results.get(atm, {}).get("strike")
strike_otm = results.get(otm, {}).get("strike")

preco_str = lambda v, l: f"R${v:.2f}" if v else "-"
strike_str = lambda v: f"R${v:.2f}" if v else "-"

print(f"  Compra 1x {atm} (strike {strike_str(strike_atm)}):")
print(f"    Bid: {preco_str(atm_bid,7)}   Ask: {preco_str(atm_ask,7)}")
print(f"  Vende 2x {otm} (strike {strike_str(strike_otm)}):")
print(f"    Bid: {preco_str(otm_bid,7)}   Ask: {preco_str(otm_ask,7)}")

if otm_bid and atm_ask:
    credito = 2 * otm_bid - atm_ask
    print(f"\n  >> Credito liquido (2x OTM bid - ATM ask): R${credito:.2f}")
    print(f"  >> Por lote (100 acoes):                    R${credito*100:.2f}")
    print(f"  >> 5 lotes:                                  R${credito*500:.2f}")
    if credito > 0:
        print(f"\n  >> OK: Credito POSITIVO! Operacao montavel.")
    else:
        print(f"\n  >> X: Credito NEGATIVO. Nao montar.")

if otm_ask and atm_bid:
    agressivo = 2 * otm_ask - atm_bid
    print(f"  (referencia: 2x OTM ask - ATM bid = R${agressivo:.2f})")

print(f"\n{'='*60}")
print("SUGESTAO DE APREGOAMENTO")
print(f"{'-'*60}")
if otm_bid and otm_ask and atm_bid and atm_ask:
    mid_atm = (atm_bid + atm_ask) / 2
    mid_otm = (otm_bid + otm_ask) / 2
    print(f"  1. VENDE 1a {otm} no ask R${otm_ask:.2f} (ou limite R${round(mid_otm+0.02,2):.2f})")
    print(f"  2. VENDE 2a {otm} no ask R${otm_ask:.2f} (ou limite R${round(mid_otm+0.01,2):.2f})")
    print(f"  3. DEPOIS COMPRA {atm} no bid R${atm_bid:.2f} (ou limite R${round(mid_atm-0.03,2):.2f})")
    print(f"  ** NUNCA compre antes de vender! **")

print(f"\n{'='*60}")
print("BOOK LIQUIDEZ (CAB>0 = tem book)")
print(f"{'-'*60}")
for cod, r in results.items():
    cab = r.get("cab", 0) or 0
    book = "TEM BOOK" if cab > 0 else "SEM BOOK"
    voc = r.get("voc", 0) or 0
    vov = r.get("vov", 0) or 0
    print(f"  {cod}: CAB={int(cab)} [{book}]  VOC={int(voc)}  VOV={int(vov)}")

rtd.desconectar()
pythoncom.CoUninitialize()
