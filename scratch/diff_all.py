import json, sqlite3

# Load JSON
with open("config/parametros_default.json") as f:
    data = json.load(f)
json_params = {}
for p in data["parametros"]:
    json_params[p["chave"]] = (p["valor"], p["estrategia"])

# Load DB
conn = sqlite3.connect("config/spreadhunter.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT chave, valor, estrategia FROM parametros_operacionais ORDER BY chave").fetchall()
conn.close()

db_params = {}
for r in rows:
    db_params[r["chave"]] = (r["valor"], r["estrategia"])

# Find ALL differences
print("DIFERENCAS DB vs JSON (em ambos os sentidos)")
print("=" * 100)
print()

all_keys = sorted(set(list(json_params.keys()) + list(db_params.keys())))

diff_count = 0
for k in all_keys:
    in_json = k in json_params
    in_db = k in db_params
    
    if not in_json:
        jv, je = "---", "---"
    else:
        jv, je = json_params[k]
    
    if not in_db:
        dv, de = "---", "---"
    else:
        dv, de = db_params[k]
    
    # Only show differences
    if jv != dv or je != de:
        diff_count += 1
        marker = " <--- DIFERENTE" if (in_json and in_db and jv != dv) else ""
        print("%-45s  DB=%-12s %-20s  JSON=%-12s %-20s%s" % (
            k, dv, de, jv, je, marker
        ))

print()
print("Total de diferencas: %d" % diff_count)
print()

# Also show params that are ONLY in DB (custom additions not in JSON)
only_db = sorted(set(db_params.keys()) - set(json_params.keys()))
print("APENAS NO DB (nao existem no JSON): %d" % len(only_db))
for k in only_db:
    v, e = db_params[k]
    print("  %-45s = %-12s [%s]" % (k, v, e))
