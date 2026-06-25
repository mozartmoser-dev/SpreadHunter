"""Monitor contínuo do book PETR4 com análise de direção + volume."""
import pythoncom
import sys
import time
import os
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.rtd_config import (
    RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA,
    RTD_CAMPO_STRIKE, RTD_CAMPO_VENCIMENTO, RTD_CAMPO_CABECALHO_BOOK,
    RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA, RTD_CAMPO_STATUS,
)
os.environ["PYTHONIOENCODING"] = "utf-8"

pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)

rtd = RTDProfit()
if not rtd.disponivel:
    print("ERRO: Profit RTD indisponivel")
    pythoncom.CoUninitialize()
    sys.exit(1)

PETR4 = "PETR4"
CODS = ["PETRT407", "PETRT394"]
CAMPOS = [RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_COMPRA, RTD_CAMPO_OFERTA_VENDA,
          RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_VOL_COMPRA, RTD_CAMPO_VOL_VENDA,
          RTD_CAMPO_STRIKE, RTD_CAMPO_VENCIMENTO]

rtd.registrar_status(PETR4)
rtd.registrar_topico(PETR4, RTD_CAMPO_ULTIMO_PRECO)
rtd.registrar_topico(PETR4, RTD_CAMPO_OFERTA_COMPRA)
rtd.registrar_topico(PETR4, RTD_CAMPO_OFERTA_VENDA)
for cod in CODS:
    for campo in CAMPOS:
        rtd.registrar_topico(cod, campo)
    rtd.registrar_status(cod)
rtd.refresh(); time.sleep(0.5)
rtd.refresh(); time.sleep(0.5)
rtd.refresh()

def lf(cod, campo):
    v = rtd.ler_campo_cache(cod, campo)
    return float(v) if v is not None else None

def ls(cod):
    return rtd.ler_status_cache(cod) or "-"

prev_spot = None
high_day = None
low_day = None
spot_history = []

print(f"{'HORA':<9} {'SPOT':<7} {'DIR':<10} {'ATM_B/A':<15} {'OTM_B/A':<15} {'VOC_ATM':<8} {'VOC_OTM':<8} {'VOV_ATM':<8} {'VOV_OTM':<8} {'SINAL'}")
print("-"*120)

while True:
    rtd.refresh()
    time.sleep(0.3)
    rtd.refresh()
    time.sleep(0.3)

    spot = lf(PETR4, RTD_CAMPO_ULTIMO_PRECO)
    if not spot:
        time.sleep(10)
        continue

    sb = lf(PETR4, RTD_CAMPO_OFERTA_COMPRA)
    sa = lf(PETR4, RTD_CAMPO_OFERTA_VENDA)

    atm_b = lf("PETRT407", RTD_CAMPO_OFERTA_COMPRA)
    atm_a = lf("PETRT407", RTD_CAMPO_OFERTA_VENDA)
    atm_voc = lf("PETRT407", RTD_CAMPO_VOL_COMPRA)
    atm_vov = lf("PETRT407", RTD_CAMPO_VOL_VENDA)

    otm_b = lf("PETRT394", RTD_CAMPO_OFERTA_COMPRA)
    otm_a = lf("PETRT394", RTD_CAMPO_OFERTA_VENDA)
    otm_voc = lf("PETRT394", RTD_CAMPO_VOL_COMPRA)
    otm_vov = lf("PETRT394", RTD_CAMPO_VOL_VENDA)

    spot_str = f"{spot:.2f}"
    atm_s = f"{atm_b:.2f}/{atm_a:.2f}" if atm_b and atm_a else "-/-"
    otm_s = f"{otm_b:.2f}/{otm_a:.2f}" if otm_b and otm_a else "-/-"

    voc_atm_s = f"{int(atm_voc)}" if atm_voc else "-"
    voc_otm_s = f"{int(otm_voc)}" if otm_voc else "-"
    vov_atm_s = f"{int(atm_vov)}" if atm_vov else "-"
    vov_otm_s = f"{int(otm_vov)}" if otm_vov else "-"

    high_day = max(high_day, spot) if high_day else spot
    low_day = min(low_day, spot) if low_day else spot

    spot_history.append(spot)
    if len(spot_history) > 6:
        spot_history.pop(0)

    # Direction (using last 6 ticks ~60s)
    dir_str = "LATERAL"
    if len(spot_history) >= 4:
        trend = spot_history[-1] - spot_history[0]
        if trend >= 0.05:
            dir_str = "SUBINDO"
        elif trend <= -0.05:
            dir_str = "DESCENDO"

    # Volume analysis
    sinal = ""
    if atm_voc and otm_voc:
        total_voc = atm_voc + otm_voc
        if dir_str == "SUBINDO" and atm_voc > otm_voc * 1.5 and atm_voc > 5000:
            sinal = f"VOL SOBE: ATM {int(atm_voc)} > OTM {int(otm_voc)}"
        elif dir_str == "DESCENDO" and otm_voc > atm_voc * 1.5 and otm_voc > 5000:
            sinal = f"VOL DESCE: OTM {int(otm_voc)} > ATM {int(atm_voc)}"
        elif dir_str == "SUBINDO" and otm_voc > atm_voc * 2 and otm_voc > 30000:
            sinal = f"DIVERGENCIA: sobe mas OTM VOC alto ({int(otm_voc)})"
        elif dir_str == "DESCENDO" and atm_voc > otm_voc * 2 and atm_voc > 30000:
            sinal = f"DIVERGENCIA: desce mas ATM VOC alto ({int(atm_voc)})"
        else:
            voc_diff = abs(atm_voc - otm_voc)
            if voc_diff < 5000 and total_voc > 20000:
                sinal = f"VOC PARADO ({int(atm_voc)}/{int(otm_voc)})"
            elif atm_voc < 5000 and otm_voc < 5000:
                sinal = "VOC ZERO - dead market"
            else:
                sinal = f"VOC A={int(atm_voc)} O={int(otm_voc)}"

    # VOV alert
    if atm_vov and otm_vov:
        if atm_vov < 1000 and atm_voc > 10000:
            sinal += " | ATM VOV sumiu (sem vendedor)"
        if otm_vov < 1000 and otm_voc > 50000:
            sinal += " | OTM VOV sumiu (comprador sem contraparte)"

    # ATM spread alert
    if atm_b and atm_a:
        spread = atm_a - atm_b
        if spread <= 0.04 and dir_str != "LATERAL":
            sinal += f" | Spread ATM {spread:.2f} (comprimido)"

    now = time.strftime("%H:%M:%S")
    print(f"{now:<9} {spot_str:<7} {dir_str:<10} {atm_s:<15} {otm_s:<15} {voc_atm_s:<8} {voc_otm_s:<8} {vov_atm_s:<8} {vov_otm_s:<8} {sinal}")

    prev_spot = spot
    time.sleep(12)
