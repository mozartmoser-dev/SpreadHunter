import sqlite3
conn = sqlite3.connect("config/spreadhunter.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT chave, valor, estrategia FROM parametros_operacionais ORDER BY estrategia, chave").fetchall()
print("Total params no DB: %d\n" % len(rows))
for r in rows:
    print("%-45s = %-10s  [%s]" % (r["chave"], r["valor"], r["estrategia"]))
conn.close()
