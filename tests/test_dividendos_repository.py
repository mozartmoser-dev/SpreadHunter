"""Proventos: chave de negocio (ativo, data_com, tipo) deduplica no SQLite.

data_pagamento fica fora da chave: quando ainda nao divulgado e NULL, e UNIQUE
no SQLite trata NULL como distinto -> cada importacao criava um duplicado novo
(ex.: EGIE3 data_com 2026-08-20, 10 registros identicos no banco real).
"""

import sqlite3

from src.infrastructure.persistence import database
from src.infrastructure.persistence.repositories.repositories import DividendoRepository


def _rec(ativo="EGIE3", tipo="Dividendo", data_com="2026-08-20",
          data_pagamento=None, valor=0.54420748):
    return {
        "ativo": ativo,
        "tipo": tipo,
        "data_com": data_com,
        "data_ex": "2026-08-21",
        "data_pagamento": data_pagamento,
        "valor": valor,
        "fonte": "statusinvest",
    }


def test_save_batch_deduplica_null_pagamento(tmp_path):
    db_path = str(tmp_path / "div.db")
    database.init_db(db_path)
    repo = DividendoRepository(db_path)
    repo.save_batch([_rec(), _rec(), _rec()])
    rows = repo.get_all()
    assert len(rows) == 1
    assert rows[0]["ativo"] == "EGIE3"
    assert rows[0]["data_com"] == "2026-08-20"


def test_save_repetido_null_pagamento_nao_duplica(tmp_path):
    db_path = str(tmp_path / "div.db")
    database.init_db(db_path)
    repo = DividendoRepository(db_path)
    for _ in range(3):
        repo.save(_rec())
    assert len(repo.get_all()) == 1


def test_upgrade_pagamento_null_para_data_atualiza_mesmo_registro(tmp_path):
    db_path = str(tmp_path / "div.db")
    database.init_db(db_path)
    repo = DividendoRepository(db_path)
    repo.save(_rec())
    repo.save(_rec(data_pagamento="2026-09-10"))
    rows = repo.get_all()
    assert len(rows) == 1
    assert rows[0]["data_pagamento"] == "2026-09-10"


def test_eventos_distintos_nao_colidem(tmp_path):
    db_path = str(tmp_path / "div.db")
    database.init_db(db_path)
    repo = DividendoRepository(db_path)
    repo.save_batch([
        _rec(tipo="Dividendo"),
        _rec(tipo="JCP"),
        _rec(ativo="PETR4"),
        _rec(data_com="2026-09-01"),
    ])
    assert len(repo.get_all()) == 4


def test_migracao_deduplica_tabela_antiga_com_pagamento(tmp_path):
    db_path = str(tmp_path / "div_antiga.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE dividendos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ativo TEXT NOT NULL,
            tipo TEXT,
            data_com DATE,
            data_ex DATE,
            data_pagamento DATE,
            data_aprovacao DATE,
            valor REAL,
            tipo_acao TEXT,
            preco_fechamento REAL,
            fonte TEXT DEFAULT 'b3',
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ativo, data_com, tipo, data_pagamento)
        )
    """)
    base = _rec()
    for ts in ("2026-08-07 11:53:47", "2026-08-10 12:08:15", "2026-08-20 13:05:37"):
        conn.execute(
            "INSERT INTO dividendos (ativo, tipo, data_com, data_ex, data_pagamento, valor, fonte, atualizado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (base["ativo"], base["tipo"], base["data_com"], base["data_ex"],
             base["data_pagamento"], base["valor"], base["fonte"], ts),
        )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    database._migrar_dividendos(conn)
    conn.commit()
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='dividendos'").fetchone()[0]
    assert "UNIQUE(ativo, data_com, tipo)" in sql
    assert "data_pagamento)" not in sql.split("UNIQUE")[-1]
    n = conn.execute("SELECT COUNT(*) FROM dividendos WHERE ativo='EGIE3'").fetchone()[0]
    conn.close()
    assert n == 1