"""Simulação com debug: mostra gap e razão de falha."""
import sys, math
sys.path.insert(0, r"C:\Users\Mozart\Projetos\Spreadhunter")
from datetime import date
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona
from src.domain.services.calendario_b3 import dc_to_du

taxa_cdi = 0.145
taxa_ir = 0.15
calda_premio_risco = 2.2
calda_desvios_cauda = 3.0
calda_ratio_max = 70

call = CalculadoraColarCalendario(
    taxa_cdi=taxa_cdi,
    premio_risco=2.0,
    taxa_ir=taxa_ir,
)

pares = [
    ("P1 PETR4 (Pc=0.90 Pp=0.20)", 25.0, 27.50, 22.50, 0.90, 0.20),
    ("P2 PETR4 (Pc=1.00 Pp=0.20)", 25.0, 27.50, 22.50, 1.00, 0.20),
    ("P3 PETR4 (Pc=1.10 Pp=0.30)", 25.0, 27.50, 22.50, 1.10, 0.30),
    ("P4 PETR4 (Pc=1.10 Pp=0.50)", 25.0, 27.50, 22.50, 1.10, 0.50),
]

print("Parametros forçados:")
print(f"  calda_premio_risco = {calda_premio_risco}x")
print(f"  calda_desvios_cauda = {calda_desvios_cauda}s")
print(f"  calda_ratio_max = {calda_ratio_max}")
print()

du_total = dc_to_du(None, None, 40)
cdi_periodo = (1 + taxa_cdi) ** (du_total / 252.0) - 1
print(f"CDI periodo ({du_total} DU): {cdi_periodo:.6f} ({cdi_periodo*100:.3f}%)")
print()

for label, S0, Kc, Kp, Pc0, Pp0 in pares:
    r = call.calcular(
        preco_ativo=S0, strike_call=Kc, strike_put=Kp,
        premio_call=Pc0, premio_put=Pp0,
        cod_call="X", cod_put="Y",
        dte_call=40, dte_put=90,
        ativo="PETR4",
        vencimento_call=date(2026, 8, 17),
        vencimento_put=date(2026, 10, 6),
    )
    if r is None or not r.viavel:
        print(f"{label:<30} INVIÁVEL")
        continue

    target_pnl = r.capital_empregado * cdi_periodo * calda_premio_risco
    gap = target_pnl - r.pnl_projetado
    print(f"{label:<30} pct_base={r.pct_cdi:.2f}x pnl_base={r.pnl_projetado:.4f} capital={r.capital_empregado:.2f} target={target_pnl:.4f} gap={gap:.4f}")

    # Testar manualmente n=1..5 pra ver o PnL nas pontas
    iv = r.iv_call / 100.0
    sigma_p = iv * math.sqrt(40 / 252.0)
    s_left = S0 * (1 - calda_desvios_cauda * sigma_p)
    s_right = S0 * (1 + calda_desvios_cauda * sigma_p)
    extra = Pc0 - max(0, S0 - Kc)

    print(f"    sigma_periodo={sigma_p:.4f} s_left={s_left:.2f} s_right={s_right:.2f} extra_call_pnl={extra:.4f}")

    for n in [1, 2, 5, 10, 20, 50]:
        pnl_spot = r.pnl_projetado + (n - 1) * extra
        dl = CalculadoraCaudaAssincrona._delta_pnl(s_left, S0, Kc, Kp, n)
        dr = CalculadoraCaudaAssincrona._delta_pnl(s_right, S0, Kc, Kp, n)
        pl = pnl_spot + dl
        pr = pnl_spot + dr
        ok = pl > 0 and pr > 0
        cap_abs = r.capital_empregado if r.capital_empregado > 0 else abs(r.capital_empregado)
        cdi = (pnl_spot / cap_abs) / cdi_periodo if cdi_periodo > 0 and cap_abs > 0 else 0.0
        print(f"    n={n:3d}: pnl_spot={pnl_spot:>8.4f} P_left={pl:>9.4f} P_right={pr:>9.4f} cdi={cdi:>6.2f}x range_ok={ok!s:>5}")

    # Cauda oficial
    cauda = CalculadoraCaudaAssincrona.calcular(
        preco_ativo=r.preco_ativo,
        strike_call=r.strike_call,
        strike_put=r.strike_put,
        premio_call=r.premio_call,
        premio_put=r.premio_put,
        dte_call=r.dte_call,
        ativo=r.ativo,
        iv_call_pct=r.iv_call,
        pnl_projetado_base=r.pnl_projetado,
        capital_empregado_base=r.capital_empregado,
        pct_cdi_base=r.pct_cdi,
        taxa_cdi=taxa_cdi,
        calda_premio_risco=calda_premio_risco,
        calda_desvios_cauda=calda_desvios_cauda,
        calda_ratio_max=calda_ratio_max,
        custo_b3_base=r.custo_b3,
        preco_compra=r.preco_compra,
    )
    if cauda is None:
        print(f"    >>> Cauda: NENHUM RATIO VIÁVEL")
    else:
        print(f"    >>> Cauda: n={cauda.ratio_call} CDI={cauda.pct_cdi_com_ratio:.2f}x range_ok={cauda.range_ok}")
    print()
