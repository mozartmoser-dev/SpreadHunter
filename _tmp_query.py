from src.infrastructure.persistence.database import get_connection
conn = get_connection()
ativos = [r[0] for r in conn.execute(
    "SELECT DISTINCT ativo FROM instrumentos_base WHERE ativo IN ('WIN$','WDO$','IND$') OR ativo LIKE 'WIN%' OR ativo LIKE 'WDO%' LIMIT 10"
).fetchall()]
print("Futuros/Indices:", ativos)
conn.close()
