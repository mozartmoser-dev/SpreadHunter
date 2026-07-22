"""
Comparacao BWB vs Protecao Simples com dados REAIS do OpenFast.
Usa precos atuais do book para calls protetoras.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import time

from src.infrastructure.persistence.database import get_db_path
from src.domain.services.calendario_b3 import dc_to_du
from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter


def bs_call(S, K, T, r, sigma):
    if T <= 1e-6 or sigma <= 1e-6: return max(S - K, 0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d1 - sigma * np.sqrt(T))


# Conectar OpenFast
print("Conectando OpenFast...")
adapter = OpenFastSocketAdapter()
if not adapter.disponivel:
    print("OpenFast indisponivel. Verifique se o servidor esta rodando.")
    sys.exit(1)

print(f"OpenFast OK. Aguardando refresh inicial...")
adapter.refresh(5000)

# Carregar dados de ontem
conn = sqlite3.connect(get_db_path())
conn.row_factory = sqlite3.Row

ativos = conn.execute("""
    SELECT DISTINCT ativo FROM historico_simulacoes
    WHERE date(detectado_em) = '2026-07-21'
      AND estagio = 'Rendimento' AND ratio_call > 1.0
    LIMIT 6
""").fetchall()

r_cont = np.log(1.145)

print(f"\n{'='*120}")
print("PROTECAO SIMPLES vs BWB — DADOS REAIS DO BOOK (MERCADO ABERTO)")
print(f"{'='*120}")

for row in ativos:
    ativo = row["ativo"]

    # Dados da operacao de ontem
    op = conn.execute("""
        SELECT ativo, preco_ativo, strike_call, strike_put,
               dte_original, dte_extra, iv_call, iv_put,
               ratio_call, premio_call, qtd_acao, be_dir, preco_compra,
               pnl_projetado, pct_cdi
        FROM historico_simulacoes
        WHERE ativo = ? AND estagio = 'Rendimento'
          AND date(detectado_em) = '2026-07-21'
        ORDER BY pct_cdi DESC LIMIT 1
    """, (ativo,)).fetchone()

    if not op:
        continue

    S = op["preco_ativo"]
    Kc = op["strike_call"]
    Pc = op["premio_call"]
    qtd = op["qtd_acao"]
    rc = op["ratio_call"]
    dte = op["dte_original"]
    iv_c = op["iv_call"] / 100.0
    be_dir = op["be_dir"]
    extra = (rc - 1.0) * qtd * Pc

    T_call = dc_to_du(None, None, dte) / 252.0
    orc_per_share = extra * 0.35 / qtd

    # BS strike alvo
    K_bs = None
    try:
        K_bs = brentq(lambda K: bs_call(S, K, T_call, r_cont, iv_c) - orc_per_share,
                      S * 1.02, S * 3.0)
    except:
        pass

    # Buscar calls reais perto do strike alvo via OpenFast
    # Pegar codigos de calls do mesmo ativo/vencimento
    calls_db = conn.execute("""
        SELECT cod_call FROM instrumentos_base
        WHERE ativo = ? AND cod_call IS NOT NULL AND cod_call != ''
        ORDER BY vencimento
        LIMIT 300
    """, (ativo,)).fetchall()

    # Ler precos reais de cada call
    calls_reais = []
    for c in calls_db:
        cod = c["cod_call"]
        ask = adapter.ler_campo_cache(cod, "ask")
        bid = adapter.ler_campo_cache(cod, "bid")
        if ask and ask > 0.005:
            calls_reais.append({"cod": cod, "ask": ask, "bid": bid})

    print(f"\n  {ativo} | S≈R${S:.2f} | Kc=R${Kc:.2f} | ratio={rc} | DTE={dte}d")
    print(f"  Credito extra: R${extra:.0f} | Orcamento 35%: R${extra*0.35:.0f} (R${orc_per_share:.4f}/acao)")
    print(f"  [BS] K prot = R${K_bs:.2f} (teorico)")
    print(f"  Calls com book: {len(calls_reais)} ")

    if calls_reais:
        # Ordenar por ask
        calls_reais.sort(key=lambda x: x["ask"])

        # Encontrar a call com ask mais proximo do orcamento
        mais_prox = min(calls_reais, key=lambda x: abs(x["ask"] - orc_per_share))
        print(f"  [BOOK] Call mais prox do orcamento: {mais_prox['cod']} ask=R${mais_prox['ask']:.4f} "
              f"(vs BS R${orc_per_share:.4f})")

        # Top 5 calls mais baratas (OTM)
        print(f"  Top 5 calls mais baratas (OTM, candidatas a protecao):")
        for c in calls_reais[:5]:
            print(f"    {c['cod']:<12s} ask=R${c['ask']:.4f} bid=R${c['bid']:.4f}")

    adapter.refresh(2000)

conn.close()
print(f"\n{'='*120}")
print("Conclusao: precos reais do book para calls OTM proximas do orcamento.")
print("Comparar BS vs Book para validar a estrategia de protecao simples.")
