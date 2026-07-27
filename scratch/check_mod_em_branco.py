import sqlite3
from src.infrastructure.persistence.database import get_db_path

db_path = get_db_path()
print("Banco:", db_path)

conn = sqlite3.connect(str(db_path))
total = conn.execute("SELECT COUNT(*) FROM instrumentos_base").fetchone()[0]
print("Total instrumentos:", total)

am = conn.execute("SELECT COUNT(*) FROM instrumentos_base WHERE tipo_opcao = 'A'").fetchone()[0]
em = conn.execute("SELECT COUNT(*) FROM instrumentos_base WHERE tipo_opcao = 'E'").fetchone()[0]
vaz = conn.execute(
    "SELECT COUNT(*) FROM instrumentos_base WHERE tipo_opcao IS NULL OR tipo_opcao = '' OR tipo_opcao NOT IN ('A', 'E')"
).fetchone()[0]

print("A:", am)
print("E:", em)
print("Vazio/Invalido:", vaz)

if vaz:
    rows = conn.execute(
        "SELECT ativo, cod_call, tipo_opcao FROM instrumentos_base WHERE tipo_opcao IS NULL OR tipo_opcao = '' OR tipo_opcao NOT IN ('A', 'E') LIMIT 10"
    ).fetchall()
    print("Amostra de invalidos:")
    for r in rows:
        print(" -", dict(r))

conn.close()
