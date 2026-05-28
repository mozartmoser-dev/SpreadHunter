from src.infrastructure.persistence.database import get_connection

conn = get_connection()
rows = conn.execute("SELECT chave, valor FROM parametros_operacionais ORDER BY estrategia, chave").fetchall()
print("\n=== Parametros no banco ===")
for row in rows:
    chave = row["chave"]
    valor = row["valor"]
    extra = ""
    if chave == "taxa_cdi":
        extra = f"  =>  {valor*100:.4f}% a.a."
    print(f"  {chave:<40} = {valor}{extra}")
conn.close()
