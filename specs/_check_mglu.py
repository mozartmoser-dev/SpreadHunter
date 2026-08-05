import sqlite3, os
db = os.path.join(os.environ['APPDATA'], 'Spreadhunter', 'spreadhunter.db')
conn = sqlite3.connect(db)

# Find MGLUH251
rows = conn.execute(
    "SELECT ativo, cod_put, cod_call, strike, vencimento FROM instrumentos_base "
    "WHERE ativo='MGLU3' AND (cod_put LIKE '%H251%' OR cod_call LIKE '%H251%')"
).fetchall()

if rows:
    for r in rows:
        print("MGLUH251 FOUND:", r)
else:
    print("MGLUH251 NOT FOUND in instrumentos_base")

# Show all MGLU3 options
rows2 = conn.execute(
    "SELECT ativo, cod_put, cod_call, vencimento FROM instrumentos_base "
    "WHERE ativo='MGLU3' ORDER BY vencimento"
).fetchall()
print(f"\nMGLU3 total options: {len(rows2)}")
for r in rows2[:40]:
    print(r)

conn.close()
