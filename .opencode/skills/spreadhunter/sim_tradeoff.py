"""Mostra trade-off: n x CDI x sigmas ate breakeven."""
import sys, math
sys.path.insert(0, r"C:\Users\Mozart\Projetos\Spreadhunter")
from datetime import date
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona
from src.domain.services.calendario_b3 import dc_to_du

taxa_cdi = 0.145

call = CalculadoraColarCalendario(taxa_cdi=taxa_cdi, premio_risco=2.0, taxa_ir=0.15)
r = call.calcular(
    preco_ativo=25.0, strike_call=27.50, strike_put=22.50,
    premio_call=1.00, premio_put=0.20,
    cod_call="X", cod_put="Y",
    dte_call=40, dte_put=90, ativo="PETR4",
    vencimento_call=date(2026, 8, 17),
    vencimento_put=date(2026, 10, 6),
)
if r is None or not r.viavel:
    print("Inviavel"); exit()

iv_call = r.iv_call / 100.0
iv_put = r.iv_put / 100.0
sigma_a = max(iv_call, iv_put)
sigma_p = sigma_a * math.sqrt(40 / 252.0)

# Para cada n (1..30), m=1.0, mostra CDI e sigmas
print(f"sigma_anual={sigma_a:.4f}  sigma_periodo={sigma_p:.4f}")
print(f"{'n':>4} {'CDI':>8} {'cap':>8} {'BE_esq':>8} {'BE_dir':>8} {'s_esq':>6} {'s_dir':>6}")
print("-"*50)

for n in range(1, 31):
    cauda = CalculadoraCaudaAssincrona.calcular(
        preco_ativo=r.preco_ativo, strike_call=r.strike_call, strike_put=r.strike_put,
        premio_call=r.premio_call, premio_put=r.premio_put,
        dte_call=r.dte_call, ativo=r.ativo, iv_call_pct=r.iv_call,
        pnl_projetado_base=r.pnl_projetado, capital_empregado_base=r.capital_empregado,
        pct_cdi_base=r.pct_cdi, taxa_cdi=taxa_cdi,
        calda_premio_risco=3.5, calda_desvios_cauda=0.5,
        calda_ratio_max=n, calda_ratio_put_min=1.0,  # so m=1.0
        calda_capital_minimo_pct=0.0,
        iv_put_pct=r.iv_put, dte_put=r.dte_put,
        preco_compra=r.preco_compra, custo_b3_base=r.custo_b3,
    )
    if cauda is None:
        continue

    be_esq = cauda.breakeven_esquerdo
    be_dir = cauda.breakeven_direito
    s_esq = (25 - be_esq) / (25 * sigma_p) if be_esq else 99
    s_dir = (be_dir - 25) / (25 * sigma_p) if be_dir else 99
    n_atual = cauda.ratio_call

    print(f"{n_atual:4d} {cauda.pct_cdi_com_ratio:>8.1f}x {cauda.pnl_com_ratio:>8.2f} "
          f"{be_esq if be_esq else 'N/A':>8} {be_dir if be_dir else 'N/A':>8} "
          f"{s_esq if s_esq < 99 else 'inf':>6} {s_dir if s_dir < 99 else 'inf':>6}")
