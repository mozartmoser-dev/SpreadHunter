import sqlite3
conn = sqlite3.connect("config/spreadhunter.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Tabelas no DB:")
for t in tables:
    cnt = conn.execute("SELECT COUNT(*) FROM \"%s\"" % t[0]).fetchone()[0]
    print("  %-35s %d registros" % (t[0], cnt))
conn.close()
