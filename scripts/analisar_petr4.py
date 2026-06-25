"""Analise PETR4 com pivot points + suportes intraday via API + RTD."""
import pythoncom
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.rtd_config import RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA
from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

# --- Dados RTD (tempo real) ---
pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
rtd = RTDProfit()
spot_rtd = None
if rtd.disponivel:
    rtd.registrar_topico("PETR4", RTD_CAMPO_ULTIMO_PRECO)
    rtd.registrar_topico("PETR4", RTD_CAMPO_OFERTA_COMPRA)
    rtd.registrar_topico("PETR4", RTD_CAMPO_OFERTA_VENDA)
    rtd.registrar_status("PETR4")
    rtd.refresh()
    time.sleep(0.3)
    rtd.refresh()
    spot_rtd = rtd.ler_campo_cache("PETR4", RTD_CAMPO_ULTIMO_PRECO)
    bid_rtd = rtd.ler_campo_cache("PETR4", RTD_CAMPO_OFERTA_COMPRA)
    ask_rtd = rtd.ler_campo_cache("PETR4", RTD_CAMPO_OFERTA_VENDA)
    status = rtd.ler_status_cache("PETR4")
    print(f"RTD: SPOT={spot_rtd:.2f}  BID={bid_rtd:.2f}  ASK={ask_rtd:.2f}  STATUS={status}")
rtd.desconectar()
pythoncom.CoUninitialize()

# --- Dados API (historico) ---
client = OpcoesNetClient()
hist = client.get_stock_history_formatted("PETR4", 504)
if not hist:
    print("API sem dados")
    sys.exit(1)

closes = [c["close"] for c in hist]
highs = [c["high"] for c in hist]
lows = [c["low"] for c in hist]
dates = [c["date"][:10] for c in hist]

ult = hist[-1]
fechamento_sex = ult["close"]
max_sex = ult["high"]
min_sex = ult["low"]

print(f"\n=== DADOS DA SESSAO ANTERIOR (sexta, {dates[-1]}) ===")
print(f"  Fechamento: R${fechamento_sex:.2f}")
print(f"  Maxima:     R${max_sex:.2f}")
print(f"  Minima:     R${min_sex:.2f}")

# --- Pivot Points (classico) ---
p = (max_sex + min_sex + fechamento_sex) / 3
r1 = 2 * p - min_sex
r2 = p + (max_sex - min_sex)
r3 = r2 + (max_sex - min_sex)
s1 = 2 * p - max_sex
s2 = p - (max_sex - min_sex)
s3 = s2 - (max_sex - min_sex)

print(f"\n=== PIVOT POINTS (classico) ===")
print(f"  R3: R${r3:.2f}")
print(f"  R2: R${r2:.2f}")
print(f"  R1: R${r1:.2f}")
print(f"  PIVOT: R${p:.2f}")
print(f"  S1: R${s1:.2f}")
print(f"  S2: R${s2:.2f}")
print(f"  S3: R${s3:.2f}")

hoje = spot_rtd or fechamento_sex
gap = hoje - fechamento_sex
gap_pct = (gap / fechamento_sex) * 100
print(f"\n  ** Spot atual: R${hoje:.2f} (gap de {gap_pct:.1f}%) **")
for nome, nivel in [("R3", r3), ("R2", r2), ("R1", r1), ("PIVOT", p), ("S1", s1), ("S2", s2), ("S3", s3)]:
    dist = abs(hoje - nivel)
    tag = " <<<" if dist < 0.30 else ""
    print(f"  {nome}: R${nivel:.2f} (dist {dist:.2f}){tag}")

# --- Gaps no grafico ---
print(f"\n=== GAPS & REGIOES IMPORTANTES ===")
# Encontra gaps no fechamento diario
for i in range(-15, 0):
    if i < -1:
        gap_baixo = min(highs[i], highs[i+1]) - max(lows[i], lows[i+1])
        if gap_baixo > 0.30:
            print(f"  Gap aberto entre {dates[i]}:{highs[i]:.2f} e {dates[i+1]}:{lows[i+1]:.2f} (R${gap_baixo:.2f})")

# --- Suportes chave para hoje ---
print(f"\n=== SUPORTES / RESISTENCIAS INTRAday ===")
low_60d = min(lows[-60:])
print(f"  Fundo 60d: R${low_60d:.2f}")
print(f"  Liquidez pega em: R$39,46 (seu relato)")
print(f"  Sexta minima: R${min_sex:.2f}")
print(f"  Fibo 50% (29.20>50.12): R$39.66")
print(f"  Fibo 61.8% (29.20>50.12): R$37.19")

# Niveis chave
niveis = {
    "Ultimo topo semanal": r1,
    "Pivot semanal": p,
    "Sexta fechamento": fechamento_sex,
    "Sexta minima": min_sex,
    "Fundo 60d": low_60d,
    "Fibo 50%": 39.66,
    "Gap low (-39.46)": 39.46,
    "Fibo 61.8%": 37.19,
}
print(f"\n  Distancias do spot (R${hoje:.2f}):")
for nome, nivel in sorted(niveis.items(), key=lambda x: abs(hoje - x[1])):
    dist = hoje - nivel
    lado = "ACIMA" if dist > 0 else ("ABAIXO" if dist < 0 else "=")
    print(f"  {lado:>6}  R${nivel:.2f}  ({abs(dist):.2f})  {nome}")
