"""Calculate how many sigmas of protection each stage provides."""
import sqlite3
from math import sqrt
from pathlib import Path

appdata = Path.home() / 'AppData' / 'Roaming' / 'Spreadhunter' / 'spreadhunter.db'
legacy = Path(r'C:\Users\Mozart\Projetos\Spreadhunter\config\spreadhunter.db')
db = appdata if appdata.exists() else (legacy if legacy.exists() else None)
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row

print(f'{"CHASSI":>10} | {"ATIVO":>6} | {"estagio":>12} | {"preco":>6} | {"IV%":>6} | {"1sigma":>7} | {"BEesq":>7} | {"BEdir":>7} | {"sig_esq":>7} | {"sig_dir":>7} | {"range_sig":>9}')
print('-' * 90)

for r in conn.execute('''
    SELECT DISTINCT h.* FROM historico_simulacoes h
    ORDER BY h.id_chassi, h.estagio
'''):
    iv_dec = r['iv_call'] / 100.0  # 34.52 -> 0.3452 (decimal)
    iv_pct = r['iv_call']
    T = r['dte_original'] / 365.0
    # 1 standard deviation = preco * IV * sqrt(T)
    one_sigma = r['preco_ativo'] * iv_dec * sqrt(T)

    be_esq_str = f'{r["be_esq"]:.2f}' if r['be_esq'] is not None else 'INF'
    be_dir_str = f'{r["be_dir"]:.2f}' if r['be_dir'] is not None else 'INF'

    if r['be_esq'] is not None:
        sig_esq = (r['be_esq'] - r['preco_ativo']) / one_sigma
        sig_esq_str = f'{sig_esq:+.2f}'
    else:
        sig_esq_str = '  INF'

    if r['be_dir'] is not None:
        sig_dir = (r['be_dir'] - r['preco_ativo']) / one_sigma
        sig_dir_str = f'{sig_dir:+.2f}'
    else:
        sig_dir_str = '  INF'

    if r['be_esq'] is not None and r['be_dir'] is not None:
        range_sig = (r['be_dir'] - r['be_esq']) / one_sigma
        range_str = f'{range_sig:.2f}'
    else:
        range_str = '  INF'

    print(f'{r["id_chassi"]:>10} | {r["ativo"]:>6} | {r["estagio"]:>12} | {r["preco_ativo"]:>6.2f} | {iv_pct:>5.1f} | {one_sigma:>7.2f} | {be_esq_str:>7} | {be_dir_str:>7} | {sig_esq_str:>7} | {sig_dir_str:>7} | {range_str:>9}')

# Summary per stage
print()
print('=== MEDIA DE SIGMAS PROTEGIDOS POR ESTAGIO ===')
print(f'{"estagio":>12} | {"N":>3} | {"sig_esq_med":>11} | {"sig_dir_med":>11} | {"%CDI_med":>8}')
print('-' * 50)

for estagio in ['Platô', 'Proteção', 'Rendimento']:
    rows = conn.execute('''
        SELECT * FROM historico_simulacoes WHERE estagio = ?
    ''', (estagio,)).fetchall()
    if not rows:
        continue
    n = len(rows)
    sig_esq_vals = []
    sig_dir_vals = []
    cdi_vals = []
    for rr in rows:
        T = rr['dte_original'] / 365.0
        iv_d = rr['iv_call'] / 100.0
        osig = rr['preco_ativo'] * iv_d * sqrt(T)
        cdi_vals.append(rr['pct_cdi'])
        if rr['be_esq'] is not None:
            sig_esq_vals.append((rr['be_esq'] - rr['preco_ativo']) / osig)
        if rr['be_dir'] is not None:
            sig_dir_vals.append((rr['be_dir'] - rr['preco_ativo']) / osig)

    sig_esq_m = f'{sum(sig_esq_vals)/len(sig_esq_vals):+.2f}' if sig_esq_vals else 'INF'
    sig_dir_m = f'{sum(sig_dir_vals)/len(sig_dir_vals):+.2f}' if sig_dir_vals else 'INF'
    cdi_m = sum(cdi_vals) / len(cdi_vals)
    print(f'{estagio:>12} | {n:>3} | {sig_esq_m:>11} | {sig_dir_m:>11} | {cdi_m:>8.4f}')

print()
print('Legenda: sig_esq = (BEesq - S0)/1sigma  |  sig_dir = (BEdir - S0)/1sigma')
print('Valor positivo = BE acima do spot (lado direito/dinheiro)')
print('INF = sem breakeven naquele lado (proteção infinita)')

conn.close()
