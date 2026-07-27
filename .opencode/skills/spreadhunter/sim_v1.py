import numpy as np
import sys
sys.path.insert(0, r"C:\\Users\\Mozart\\Projetos\\Spreadhunter")
from datetime import date
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona
from src.infrastructure.persistence.database import get_db_path
from src.infrastructure.persistence.repositories.repositories import ParametroRepository

# Carrega parâmetros REAIS do banco (não usar defaults)
repo = ParametroRepository(get_db_path())
def _p(chave, default):
    p = repo.get_by_chave(chave)
    return p.valor if p else default

premio_risco_colar_calendario = float(_p("premio_risco_colar_calendario", 2.0))
taxa_cdi = float(_p("taxa_cdi", 0.1450))
taxa_emol = float(_p("taxa_emolumento_pct", 0.00025))
taxa_liq = float(_p("taxa_liquidacao_pct", 0.000275))
taxa_ir = float(_p("taxa_ir_pct", 0.15))

calda_habilitado = float(_p("calda_habilitado", 1.0))
calda_premio_risco = float(_p("calda_premio_risco", 2.5))
calda_desvios_cauda = float(_p("calda_desvios_cauda", 3.0))
calda_ratio_max = int(float(_p("calda_ratio_max", 50)))

print("=== PARAMETROS REAIS DO BANCO ===")
print(f"premio_risco_colar_calendario = {premio_risco_colar_calendario}")
print(f"taxa_cdi = {taxa_cdi*100:.2f}% (emol={taxa_emol*100:.3f}% liq={taxa_liq*100:.3f}% ir={taxa_ir*100:.2f}%)")
print(f"calda_habilitado = {calda_habilitado}")
print(f"calda_premio_risco = {calda_premio_risco}")
print(f"calda_desvios_cauda = {calda_desvios_cauda}")
print(f"calda_ratio_max = {calda_ratio_max}")
print()

# Pares PETR4 tipicos viaveis (premiacao ~2.20x a ~2.50x)
call = CalculadoraColarCalendario(
    taxa_cdi=taxa_cdi,
    premio_risco=premio_risco_colar_calendario,
    taxa_ir=taxa_ir,
)
pares_petr4 = [
    ("P1 PETR4 (Pc=0.90 Pp=0.20)",  25.0, 27.50, 22.50, 0.90, 0.20),
    ("P2 PETR4 (Pc=1.00 Pp=0.20)",  25.0, 27.50, 22.50, 1.00, 0.20),
    ("P3 PETR4 (Pc=1.10 Pp=0.30)",  25.0, 27.50, 22.50, 1.10, 0.30),
    ("P4 PETR4 (Pc=1.10 Pp=0.50)",  25.0, 27.50, 22.50, 1.10, 0.50),
]

print("=== PARES PETR4 BASE (1:1:1, sem cauda) ===")
for label, S0, Kc, Kp, Pc0, Pp0 in pares_petr4:
    r = call.calcular(
        preco_ativo=S0, strike_call=Kc, strike_put=Kp,
        premio_call=Pc0, premio_put=Pp0,
        cod_call="X", cod_put="Y",
        dte_call=40, dte_put=90,
        ativo="PETR4",
        vencimento_call=date(2026, 8, 17),
        vencimento_put=date(2026, 10, 6),
    )
    if r is None:
        print(f"  {label}  -> IV nao convergiu")
        continue
    print(f"  {label}: pct_cdi={r.pct_cdi:.2f}x viavel={r.viavel} "
          f"iv_call={r.iv_call:.1f}% iv_put={r.iv_put:.1f}% "
          f"tipo={r.tipo.name}")
print()
