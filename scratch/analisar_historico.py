"""
Comparação: antes vs depois das otimizações no Collar Calendário.
"""
import sqlite3
from pathlib import Path
import os
from collections import defaultdict

appdata = os.environ.get('APPDATA', '')
db_path = Path(appdata) / 'Spreadhunter' / 'spreadhunter.db'
if not db_path.exists():
    db_path = Path('config/spreadhunter.db')

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Group by (ativo, strike_call, strike_put)
cur = conn.execute("""
    SELECT ativo, strike_call, strike_put, estagio,
           ratio_call, ratio_put, pct_cdi,
           pnl_cauda_esq, pnl_cauda_dir, be_esq, be_dir
    FROM historico_simulacoes
    ORDER BY ativo, strike_call, strike_put, estagio
""")
rows = cur.fetchall()

oport_map = defaultdict(dict)
for r in rows:
    key = (r['ativo'], r['strike_call'], r['strike_put'])
    oport_map[key][r['estagio']] = {
        'ratio_call': r['ratio_call'],
        'ratio_put': r['ratio_put'],
        'pct_cdi': r['pct_cdi'],
        'pnl_esq': r['pnl_cauda_esq'],
        'pnl_dir': r['pnl_cauda_dir'],
        'be_esq': r['be_esq'],
        'be_dir': r['be_dir'],
    }

uniq_oports = len(oport_map)
total_variants = len(rows)

# Stats
spreads = []
for key, stages in oport_map.items():
    if len(stages) >= 2:
        cdis = [s['pct_cdi'] for s in stages.values()]
        spreads.append(max(cdis) - min(cdis))

avg_spread_pp = sum(spreads)/len(spreads)*100 if spreads else 0
max_spread_pp = max(spreads)*100 if spreads else 0
min_spread_pp = min(spreads)*100 if spreads else 0

# Most differentiated
diff_oports = sorted(oport_map.items(),
    key=lambda x: max(s['pct_cdi'] for s in x[1].values()) - min(s['pct_cdi'] for s in x[1].values()),
    reverse=True)

# Best per ativo
cur2 = conn.execute("""
    SELECT ativo,
           MAX(pct_cdi) as melhor_cdi,
           ROUND(AVG(pct_cdi), 4) as cdi_medio,
           COUNT(*) as n
    FROM historico_simulacoes
    GROUP BY ativo
    ORDER BY melhor_cdi DESC
""")
por_ativo = cur2.fetchall()

# Top 3 global
cur3 = conn.execute("""
    SELECT ativo, strike_call, strike_put, estagio,
           ratio_call, ratio_put, pct_cdi,
           pnl_cauda_esq, pnl_cauda_dir
    FROM historico_simulacoes
    ORDER BY pct_cdi DESC LIMIT 3
""")
top3 = cur3.fetchall()

# ===== PRINT =====
print("=" * 90)
print("RESUMO DAS OTIMIZACOES - COLLAR CALENDARIO")
print("=" * 90)

print(f"\nOportunidades unicas: {uniq_oports}")
print(f"Variantes geradas:    {total_variants}")
print(f"CDI medio entre variantes:  {avg_spread_pp:.4f} p.p.")
print(f"Maior spread de CDI:        {max_spread_pp:.4f} p.p.")
print(f"Menor spread de CDI:        {min_spread_pp:.4f} p.p.")

print(f"\n--- Top 5 com MAIOR diferenciacao entre variantes ---")
for key, stages in diff_oports[:5]:
    cdis = {e: s['pct_cdi'] for e, s in stages.items()}
    print(f"  {key[0]:8s} C={key[1]:>6.2f} P={key[2]:>6.2f}")
    for estagio in ['Rendimento', 'Protecao', 'Plato']:
        if estagio in stages:
            s = stages[estagio]
            be_e = f"{s['be_esq']:.2f}" if s['be_esq'] else 'inf'
            print(f"    {estagio:12s} rC={s['ratio_call']:.1f} rP={s['ratio_put']:.1f}  "
                  f"CDI={s['pct_cdi']:.2%}  PnL=({s['pnl_esq']:.0f},{s['pnl_dir']:.0f})  "
                  f"BE=({be_e},{s['be_dir']:.2f})")
    print()

print("--- Melhores oportunidades por ativo ---")
for r in por_ativo:
    print(f"  {r['ativo']:8s}  melhor CDI={r['melhor_cdi']:.2%}  "
          f"CDI medio={r['cdi_medio']:.2%}  variantes={r['n']}")

print(f"\n--- Top 3 globais ---")
for r in top3:
    print(f"  {r['ativo']:8s} C={r['strike_call']:.2f} P={r['strike_put']:.2f}  "
          f"{r['estagio']:12s} rC={r['ratio_call']:.1f} rP={r['ratio_put']:.1f}  "
          f"CDI={r['pct_cdi']:.2%}  PnL=({r['pnl_cauda_esq']:.0f},{r['pnl_cauda_dir']:.0f})")

print("\n" + "=" * 90)
print("O QUE FOI OTIMIZADO (git log)")
print("=" * 90)
print("""
53e15df  Motor de Engenharia de Payoff (Otimizado)
   22 arquivos, +1430/-30 linhas
   - calculadora_cauda_assincrona.py: filtro 3s (PnL>=0) + CDI target
   - monitor_worker.py: pipeline _processar_otimizado()
   - database.py + repositories.py: tabela historico_simulacoes
   - historico_simulacoes_dialog.py: visualizacao + limpar
   - parametros_default.json: otimizado_*, colar_qul_min_*
   - 3 variantes: Rendimento, Protecao, Plato (Base pulado)

f0bdd21  Parametros qtd_acao/qtd_call/qtd_put
   - Variantes respeitam lote minimo

224652e  Dashboard S/M badges + Top N por ativo
   - UI com indicadores de tamanho
""")

# Diagnosis
print("=" * 90)
print("DIAGNOSTICO")
print("=" * 90)
if avg_spread_pp < 0.1:
    print("[!] Spread CDI entre variantes muito baixo (<0.1 p.p.)")
    print("    As 3 variantes (Rendimento/Protecao/Plato) sao quase identicas.")
    print("    Sugestao: reduzir otimizado_ratio_put_step de 0.10 para 0.05")
    print("    para gerar combinacoes mais variadas de ratio_call/ratio_put.\n")
else:
    print("[OK] Spread CDI entre variantes: {avg_spread_pp:.4f} p.p. - aceitavel\n")

conn.close()
