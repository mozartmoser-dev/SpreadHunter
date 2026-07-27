import json

# DB seed params (from database.py _seed_parametros_colar)
db_params = {}
raw = """premio_risco_colar|0.7|COLAR
colar_dist_max_pct|0.15|COLAR
calendario_strike_diff_max|1|COLLAR_CALENDARIO
premio_risco_colar_calendario|0.9|COLLAR_CALENDARIO
calendario_call_otm_max|0.15|COLLAR_CALENDARIO
taxa_emolumento_pct|0.00025|GERAL
taxa_liquidacao_pct|0.000275|GERAL
colar_qtd_ativo|100|COLAR
colar_prof_ativo|1|COLAR
colar_qtd_call|100|COLAR
colar_prof_call|-1|COLAR
colar_qtd_put|100|COLAR
colar_prof_put|-1|COLAR
calendario_qtd_ativo|100|COLLAR_CALENDARIO
calendario_prof_ativo|1|COLLAR_CALENDARIO
calendario_qtd_call|100|COLLAR_CALENDARIO
calendario_prof_call|-1|COLLAR_CALENDARIO
calendario_qtd_put|100|COLLAR_CALENDARIO
calendario_prof_put|-1|COLLAR_CALENDARIO
colar_qul_min_put|100|COLAR
colar_qul_min_call|100|COLAR
colar_risco_baixo_vov_min|1000|COLAR
ranking_peso_colar_pop|3.0|COLAR
ranking_peso_colar_cdi|2.0|COLAR
ranking_peso_colar_risco|1.0|COLAR
taxa_ir_pct|0.15|GERAL
rtd_refresh_timeout_ms|5000|GERAL
ex_dividendo_lookback_dias|5|GERAL
elegibilidade_strike_max_pct|0.70|BOX_SINTETICO
dte_call_min|25|COLLAR_CALENDARIO
dte_call_max|60|COLLAR_CALENDARIO
dte_extra_min|30|COLLAR_CALENDARIO
dte_extra_max|120|COLLAR_CALENDARIO
dte_total_max|180|COLLAR_CALENDARIO
import_max_months|9|IMPORTACAO
white_list_box4p||BOX_4P
limiar_classificacao_calendario|0.15|COLLAR_CALENDARIO
be_search_range_mult|0.15|COLLAR_CALENDARIO
white_list_colar_calendario||COLLAR_CALENDARIO
white_list_colar||COLAR
telegram_cleanup_timeout|300|TELEGRAM
ranking_peso_theta|3.0|COLLAR_CALENDARIO
ranking_peso_cdi|2.0|COLLAR_CALENDARIO
ranking_peso_sigma|2.0|COLLAR_CALENDARIO
ranking_peso_credito|1.0|COLLAR_CALENDARIO
ranking_peso_liquidez|0.5|COLLAR_CALENDARIO
ranking_peso_iv_rank|25.0|COLLAR_CALENDARIO
ranking_peso_dist_strike|25.0|COLLAR_CALENDARIO
ranking_peso_theta_margin|25.0|COLLAR_CALENDARIO
ranking_peso_vega|10.0|COLLAR_CALENDARIO
ranking_peso_liquidez_iv|10.0|COLLAR_CALENDARIO
ranking_peso_risco_max|5.0|COLLAR_CALENDARIO
mpp_habilitado|1|MPP
mpp_peso_oi|0.15|MPP
mpp_peso_volume|0.10|MPP
mpp_peso_curvatura_iv|0.10|MPP
mpp_peso_paridade|0.25|MPP
mpp_peso_spread|0.20|MPP
mpp_peso_profundidade|0.10|MPP
mpp_peso_imbalance|0.05|MPP
mpp_peso_spread_anomalia|0.05|MPP
mpp_spread_history_len|200|MPP
mpp_spread_min_anomalia|0.02|MPP
mpp_curvatura_normalizador|0.10|MPP
mpp_oi_peso_absoluto|0.40|MPP
mpp_oi_peso_concentracao|0.60|MPP
mpp_oi_cap_absoluto|10000|MPP
mpp_dte_fator_min|0.60|MPP
mpp_dte_ideal_min|10|MPP
mpp_dte_ideal_max|25|MPP
mpp_instantaneo_interval|4|MPP
mpp_persistencia_max_mult|0.50|MPP
mpp_persistencia_divisor|20|MPP
box_premio_risco|1.08|MPP
mpp_paridade_normalizador|0.10|MPP
mpp_erro_paridade_limiar|0.02|MPP
mpp_peso_estrutural|0.35|MPP
mpp_peso_instantaneo|0.65|MPP
mpp_bonus_max|0.15|MPP
mpp_bonus_taxa|0.25|MPP
mre_lote_base|100|MRE
mre_profundidade_max_pct|0.20|MRE
perf_carga_inteligente|1|PERFORMANCE
perf_range_min|-70|PERFORMANCE
perf_range_max|70|PERFORMANCE
perf_limite_meses|6|PERFORMANCE
perf_dias_minimos|7|PERFORMANCE
onda2_dte_min|7|PERFORMANCE
onda2_dte_max|180|PERFORMANCE
box_scan_interval|5|BOX_4P"""
for line in raw.strip().split("\n"):
    chave, valor, estrategia = line.split("|", 2)
    db_params[chave] = (valor, estrategia)

# JSON params
with open("config/parametros_default.json") as f:
    data = json.load(f)

json_params = {}
for p in data["parametros"]:
    json_params[p["chave"]] = (p["valor"], p["estrategia"])

# Stats
print(f"Params no JSON: {len(json_params)}")
print(f"Params no DB seed: {len(db_params)}")
print()

# In JSON but not in DB seed
only_json = set(json_params) - set(db_params)
if only_json:
    print("=== APENAS NO JSON (nao estao no DB seed) ===")
    for k in sorted(only_json):
        v, e = json_params[k]
        print(f"  {k:45s} = {v:10s}  [{e}]")

# In DB seed but not in JSON
only_db = set(db_params) - set(json_params)
if only_db:
    print("=== APENAS NO DB seed (nao estao no JSON) ===")
    for k in sorted(only_db):
        v, e = db_params[k]
        print(f"  {k:45s} = {v:10s}  [{e}]")

# Same key, different values
diffs = []
for k in sorted(set(db_params) & set(json_params)):
    if db_params[k][0] != json_params[k][0]:
        diffs.append((k, db_params[k][0], json_params[k][0]))
if diffs:
    print(f"\n=== VALORES DIFERENTES ({len(diffs)}) ===")
    print(f"{'CHAVE':45s} {'DB SEED':12s} {'JSON':12s}")
    print("-"*70)
    for k, dbv, jsv in diffs:
        marker = " <<<" if dbv != jsv else ""
        print(f"  {k:45s} {dbv:12s} {jsv:12s}{marker}")
