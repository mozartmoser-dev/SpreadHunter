import tempfile, pathlib
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import ParametroRepository

# create temp file
p = pathlib.Path('tmp_test_param.db')
conn = init_db(p)
conn.close()
repo = ParametroRepository(p)
repo.seed_defaults()
rows = repo.get_by_estrategia('BOX')
print('count', len(rows))
print([ (r.chave, r.valor) for r in rows])
