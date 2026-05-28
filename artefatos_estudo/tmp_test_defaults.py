import sqlite3
from src.infrastructure.persistence.database import SCHEMA
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
conn = sqlite3.connect(':memory:')
conn.executescript(SCHEMA)
conn.commit()
repo = ParametroRepository()
repo.seed_defaults()
rows = conn.execute('SELECT * FROM parametros_operacionais').fetchall()
print('count', len(rows))
print([row['estrategia'] for row in rows])
