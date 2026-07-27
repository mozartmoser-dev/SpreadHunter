"""Analisar se os BEs cobrem o 3-sigma."""
import sqlite3, math
from pathlib import Path
import os

appdata = os.environ.get('APPDATA', '')
db = Path(appdata) / 'Spreadhunter' / 'spreadhunter.db'
if not db.exists():
    db = Path('config/spreadhunter.db')

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row

cur = conn.execute("""
    SELECT id_chassi, ativo, estagio, preco_ativo, strike_call, strike_put,
           dte_original, iv_call, ratio_call, ratio_put,
           pct_cdi, pnl_cauda_esq, pnl_cauda_dir, be_esq, be_dir
    FROM historico_simulacoes
    ORDER BY id_chassi, estagio
""")
rows = cur.fetchall()

# Group by chassi
from collections import OrderedDict
oport_map = OrderedDict()
for r in rows:
    ch = r['id_chassi']
    if ch not in oport_map:
        oport_map[ch] = []
    oport_map[ch].append(r)

print("=" * 120)
print("BE vs 3-SIGMA - COLLAR CALENDARIO")
print("=" * 120)
print(f"\nChassis: {len(oport_map)}   Variantes: {len(rows)}")
print()

protegido_esq = 0
protegido_dir = 0
protegido_ambos = 0
total_var = 0

for ch, variants in oport_map.items():
    v0 = variants[0]
    S0 = v0['preco_ativo']
    iv = v0['iv_call'] / 100.0
    dte = v0['dte_original']
    sigma_p = iv * math.sqrt(dte / 252.0) if dte > 0 else 0
    
    s3_l = S0 * (1 - 3 * sigma_p)
    s3_r = S0 * (1 + 3 * sigma_p)
    
    ativo = v0['ativo']
    strike_c = v0['strike_call']
    strike_p = v0['strike_put']
    
    print(f"  {ativo:8s} C={strike_c:>6.2f} P={strike_p:>6.2f}  "
          f"S0={S0:.2f}  sigma_p={sigma_p:.4f}  "
          f"3s=[{s3_l:>7.2f}, {s3_r:>7.2f}]")
    
    for v in variants:
        be_e = v['be_esq']
        be_d = v['be_dir']
        
        ok_esq = be_e is not None and be_e <= s3_l
        ok_dir = be_d is not None and be_d >= s3_r
        
        if ok_esq: protegido_esq += 1
        if ok_dir: protegido_dir += 1
        if ok_esq and ok_dir: protegido_ambos += 1
        total_var += 1
        
        be_e_str = f"{be_e:.2f}" if be_e else "  inf"
        ok_e_str = "OK" if ok_esq else "--"
        ok_d_str = "OK" if ok_dir else "--"
        
        print(f"    {v['estagio']:12s} rC={v['ratio_call']:.1f} rP={v['ratio_put']:.1f}  "
              f"CDI={v['pct_cdi']:.2%}  BE=({be_e_str:>6},{be_d:.2f})  "
              f"[{ok_e_str}/{ok_d_str}]  "
              f"gap_esq={be_e - s3_l:.2f}" if be_e else f"[{ok_e_str}/{ok_d_str}]")
    
    print()

print("=" * 120)
print(f"RESUMO: BE cobre o 3-sigma?")
print(f"  BE esquerdo dentro (<= 3s_l): {protegido_esq}/{total_var} ({protegido_esq/total_var*100:.0f}%)")
print(f"  BE direito dentro (>= 3s_r):  {protegido_dir}/{total_var} ({protegido_dir/total_var*100:.0f}%)")
print(f"  Ambos protegidos:              {protegido_ambos}/{total_var} ({protegido_ambos/total_var*100:.0f}%)")
print(f"  % nao protegido:               {(total_var-protegido_ambos)/total_var*100:.0f}%")

conn.close()
