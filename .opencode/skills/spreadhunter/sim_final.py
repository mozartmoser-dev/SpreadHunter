"""Sim: desvios=1, ratio_max=300."""
import sys, math
sys.path.insert(0, r"C:\Users\Mozart\Projetos\Spreadhunter")
from datetime import date
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona

r = CalculadoraColarCalendario(taxa_cdi=0.145, premio_risco=2.0, taxa_ir=0.15).calcular(
    preco_ativo=25.0, strike_call=27.50, strike_put=22.50,
    premio_call=1.00, premio_put=0.20,
    cod_call="X", cod_put="Y",
    dte_call=40, dte_put=90, ativo="PETR4",
    vencimento_call=date(2026,8,17), vencimento_put=date(2026,10,6),
)
if not r or not r.viavel: print("Inv"); exit()

sp = (r.iv_call/100.0)*math.sqrt(40/252)
print(f"Base={r.pct_cdi:.1f}x IV={r.iv_call:.1f}% 1s=R${25*sp:.1f}")
print(f"{'n_max':>6} {'CDI':>8} {'BE_dir':>8} {'s_dir':>6}")
print("-"*35)

for mx in [50, 100, 150, 200, 300, 500]:
    c = CalculadoraCaudaAssincrona.calcular(
        preco_ativo=r.preco_ativo, strike_call=r.strike_call, strike_put=r.strike_put,
        premio_call=r.premio_call, premio_put=r.premio_put,
        dte_call=r.dte_call, ativo=r.ativo, iv_call_pct=r.iv_call,
        pnl_projetado_base=r.pnl_projetado, capital_empregado_base=r.capital_empregado,
        pct_cdi_base=r.pct_cdi, taxa_cdi=0.145,
        calda_premio_risco=3.5, calda_desvios_cauda=1.0,
        calda_ratio_max=mx, calda_ratio_put_min=0.3, calda_ratio_put_step=0.05,
        iv_put_pct=r.iv_put, dte_put=r.dte_put,
        preco_compra=r.preco_compra, custo_b3_base=r.custo_b3,
    )
    if c is None:
        print(f"{1+mx/100:>6.2f}x {'sem':>15}")
        continue
    sd = (c.breakeven_direito-25)/(25*sp) if c.breakeven_direito else 99
    print(f"{c.ratio_call:>6.2f}x {c.pct_cdi_com_ratio:>7.1f}x {c.breakeven_direito or 0:>8.2f} {sd:>5.2f}s")
