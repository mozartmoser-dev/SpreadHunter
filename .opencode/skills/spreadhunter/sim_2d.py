"""Simulacao: calda_ratio_max=40 (+40%), passo 1%."""
import sys
sys.path.insert(0, r"C:\Users\Mozart\Projetos\Spreadhunter")
from datetime import date
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona

taxa_cdi = 0.145

call = CalculadoraColarCalendario(taxa_cdi=taxa_cdi, premio_risco=2.0, taxa_ir=0.15)

pares = [
    ("P1 (Pc=0.90 Pp=0.20)", 25.0, 27.50, 22.50, 0.90, 0.20),
    ("P2 (Pc=1.00 Pp=0.20)", 25.0, 27.50, 22.50, 1.00, 0.20),
    ("P3 (Pc=1.10 Pp=0.30)", 25.0, 27.50, 22.50, 1.10, 0.30),
    ("P4 (Pc=1.10 Pp=0.50)", 25.0, 27.50, 22.50, 1.10, 0.50),
]

print(f"{'Par':<22} {'base':>5} {'n':>5} {'m':>5} {'CDI':>8} {'P_left':>8} {'P_right':>8} {'BE_esq':>8} {'BE_dir':>8}")
print("-"*80)

for label, S0, Kc, Kp, Pc, Pp in pares:
    r = call.calcular(
        preco_ativo=S0, strike_call=Kc, strike_put=Kp,
        premio_call=Pc, premio_put=Pp,
        cod_call="X", cod_put="Y",
        dte_call=40, dte_put=90, ativo="PETR4",
        vencimento_call=date(2026, 8, 17),
        vencimento_put=date(2026, 10, 6),
    )
    if r is None or not r.viavel:
        print(f"{label:<22} INVIAVEL")
        continue

    cauda = CalculadoraCaudaAssincrona.calcular(
        preco_ativo=r.preco_ativo, strike_call=r.strike_call, strike_put=r.strike_put,
        premio_call=r.premio_call, premio_put=r.premio_put,
        dte_call=r.dte_call, ativo=r.ativo, iv_call_pct=r.iv_call,
        pnl_projetado_base=r.pnl_projetado, capital_empregado_base=r.capital_empregado,
        pct_cdi_base=r.pct_cdi, taxa_cdi=taxa_cdi,
        calda_premio_risco=3.5, calda_desvios_cauda=0.5,
        calda_ratio_max=40, calda_ratio_put_min=0.3,
        calda_ratio_put_step=0.01,
        calda_capital_minimo_pct=0.0,
        iv_put_pct=r.iv_put, dte_put=r.dte_put,
        preco_compra=r.preco_compra, custo_b3_base=r.custo_b3,
    )

    if cauda is None:
        print(f"{label:<22} {r.pct_cdi:>5.2f}x {'---':>5} {'---':>5} {'---':>8} {'---':>8} {'---':>8} {'---':>8} {'---':>8}")
    else:
        bes = f"{cauda.breakeven_esquerdo:.2f}" if cauda.breakeven_esquerdo else "N/A"
        bds = f"{cauda.breakeven_direito:.2f}" if cauda.breakeven_direito else "N/A"
        print(f"{label:<22} {r.pct_cdi:>5.2f}x {cauda.ratio_call:>5.2f}x {cauda.ratio_put:>5.2f}x "
              f"{cauda.pct_cdi_com_ratio:>8.1f}x {cauda.pnl_na_cauda_esquerda:>8.4f} {cauda.pnl_na_cauda_direita:>8.4f} "
              f"{bes:>8} {bds:>8}")
