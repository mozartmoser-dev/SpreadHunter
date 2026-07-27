"""Testa migração de fonte_market_data 0/1 → profit/openfast."""
import tempfile, os, sqlite3, sys
sys.path.insert(0, '.')

tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
db_path = tmp.name
tmp.close()

conn = sqlite3.connect(db_path)
conn.executescript("""
    CREATE TABLE parametros_operacionais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chave TEXT UNIQUE NOT NULL,
        valor TEXT NOT NULL,
        estrategia TEXT NOT NULL,
        descricao TEXT
    );
    INSERT INTO parametros_operacionais (chave, valor, estrategia, descricao)
    VALUES ('fonte_market_data', '0', 'GERAL', 'test');
""")
conn.commit()

from src.infrastructure.persistence.database import _migrar_fonte_market_data

# Test 0 -> profit
_migrar_fonte_market_data(conn)
row = conn.execute("SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'").fetchone()
assert row[0] == 'profit', f'Expected profit, got {row[0]}'
print('OK: migration 0 -> profit')

# Test 1 -> openfast
conn.execute("UPDATE parametros_operacionais SET valor = '1' WHERE chave = 'fonte_market_data'")
conn.commit()
_migrar_fonte_market_data(conn)
row = conn.execute("SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'").fetchone()
assert row[0] == 'openfast', f'Expected openfast, got {row[0]}'
print('OK: migration 1 -> openfast')

# Test idempotence for openfast
_migrar_fonte_market_data(conn)
row = conn.execute("SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'").fetchone()
assert row[0] == 'openfast', 'Migration changed already-migrated value!'
print('OK: migration idempotent for openfast')

# Test idempotence for profit
conn.execute("UPDATE parametros_operacionais SET valor = 'profit' WHERE chave = 'fonte_market_data'")
conn.commit()
_migrar_fonte_market_data(conn)
row = conn.execute("SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'").fetchone()
assert row[0] == 'profit', 'Migration changed already-migrated profit value!'
print('OK: migration idempotent for profit')

conn.close()
os.unlink(db_path)
print('ALL OK: migration segura e idempotente')
