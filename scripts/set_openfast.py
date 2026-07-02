"""Altera fonte_market_data para OpenFast Socket no banco de produção."""
import sqlite3
import os
from pathlib import Path

db_path = Path(os.environ["APPDATA"]) / "Spreadhunter" / "spreadhunter.db"
print(f"Banco: {db_path}")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

row = cursor.execute("SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'").fetchone()
print(f"Valor atual: {row[0] if row else 'N/A'}")

cursor.execute("UPDATE parametros_operacionais SET valor = 'openfast' WHERE chave = 'fonte_market_data'")
conn.commit()

row = cursor.execute("SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'").fetchone()
print(f"Novo valor: {row[0] if row else 'N/A'}")
conn.close()
print("OK - fonte_market_data alterado para openfast (Open Fast Socket)")
