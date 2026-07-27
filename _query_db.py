import sys; sys.path.insert(0, '.')
from src.infrastructure.persistence.database import get_db_path
import sqlite3, json

conn = sqlite3.connect(get_db_path())
cur = conn.cursor()

# 1) Latest 3 collar cal entries from calendario_resultados and historico_simulacoes
print("=== calendario_resultados - latest 3 ===")
cur.execute("SELECT * FROM calendario_resultados ORDER BY id DESC LIMIT 3")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
if rows:
    for i, row in enumerate(rows):
        print(f'\n--- Entry {i+1} ---')
        for c, v in zip(cols, row):
            print(f'  {c}: {v}')
else:
    print('  (empty)')

# 2) Most recent 3 in historico_simulacoes
print("\n=== historico_simulacoes - latest 3 ===")
cur.execute("SELECT id, id_chassi, estagio, ativo, preco_ativo, strike_call, strike_put, ratio_call, ratio_put, dte_original, pct_cdi, pnl_cauda_esq, pnl_cauda_dir, be_esq, be_dir, viavel, custo_protecao_total, pnl_liquido_pos_protecao, tipo_estrategia, detectado_em FROM historico_simulacoes ORDER BY id DESC LIMIT 3")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
for i, row in enumerate(rows):
    print(f'\n--- Entry {i+1} ---')
    for c, v in zip(cols, row):
        print(f'  {c}: {v}')

# 3) Parametros matching the keywords
print("\n=== parametros_operacionais (calendario/ratio/protecao/cauda/bwb/otimizado/calda) ===")
keywords = ['calendario', 'ratio', 'protecao', 'cauda', 'bwb',
            'otimizado', 'calda', 'limite_protecao', 'cab_minimo',
            'n_sigma', 'fator_seguranca', 'desvios', 'sigma_rendimento',
            'premio_risco_colar_calendario', 'strike_diff', 'call_otm',
            'dte_call', 'dte_extra', 'dte_total', 'limiar_classificacao',
            'be_search', 'calda_preco_min', 'cab', 'ranking_peso',
            'limitar_classificacao']
likes = ' OR '.join(['chave LIKE ?' for _ in keywords])
params = [f'%{k}%' for k in keywords]
cur.execute(f"SELECT chave, valor, estrategia FROM parametros_operacionais WHERE {likes} ORDER BY chave", params)
for r in cur.fetchall():
    print(f'  {r[0]:40s} = {r[1]:>10s}  [{r[2]}]')

conn.close()
