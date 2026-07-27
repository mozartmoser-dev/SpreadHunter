import json, sqlite3

conn = sqlite3.connect("config/spreadhunter.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT chave, valor, estrategia, descricao FROM parametros_operacionais ORDER BY estrategia, chave").fetchall()
conn.close()

# Build JSON structure matching existing format
PARAMS_INFO = {
    "taxa_cdi": "Taxa CDI/Selic",
    "taxa_emolumento_pct": "Taxa de emolumento B3 (0.025%)",
    "taxa_liquidacao_pct": "Taxa de liquidacao B3 (0.0275%)",
    "taxa_registro_pct": "Taxa de registro B3 para opcoes",
    "taxa_iss_pct": "ISS sobre corretagem",
    "taxa_ir_pct": "Aliquota IR (15% swing trade)",
    "tema_visual": "Tema Visual (0=Marinho, 1=Grafite, 2=Charcoal)",
    "rtd_refresh_timeout_ms": "Timeout RTD RefreshData (ms, 0=sem timeout)",
    "ex_dividendo_lookback_dias": "Janela ex-div (dias) p/ refresh RTD",
    "import_max_months": "Meses a frente para importar series",
    "black_list_import": "Blacklist de ativos (separados por virgula)",
}

parametros = []
for r in rows:
    desc = PARAMS_INFO.get(r["chave"]) or r["descricao"] or ""
    if desc is None:
        desc = ""
    valor = r["valor"]
    valor = str(valor)
    
    parametros.append({
        "chave": r["chave"],
        "valor": valor,
        "estrategia": r["estrategia"],
        "descricao": desc,
    })

output = {
    "_comment": "Blueprint de parametros do SpreadHunter. Valores usados como seed na criacao do banco. Altere aqui para customizar sua instalacao.",
    "parametros": parametros,
}

with open("config/parametros_default.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print("JSON atualizado com %d parametros do DB." % len(parametros))
