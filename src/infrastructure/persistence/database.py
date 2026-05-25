import sqlite3
from pathlib import Path

DB_NAME = "spreadhunter.db"


def get_db_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "config" / DB_NAME


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    _migrar_dividendos(conn)
    _seed_parametros_colar(conn)
    conn.commit()
    return conn


def _seed_parametros_colar(conn):
    params = [
        ("premio_risco_colar", "1.0", "COLAR", "Premio risco Colar (x CDI)"),
        ("colar_dist_max_pct", "0.3", "COLAR", "Distancia maxima do strike (%)"),
    ]
    for chave, valor, estrategia, descricao in params:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO parametros_operacionais (chave, valor, estrategia, descricao) VALUES (?, ?, ?, ?)",
                (chave, valor, estrategia, descricao),
            )
        except sqlite3.OperationalError:
            pass


def _migrar_dividendos(conn):
    """Adiciona colunas data_com e data_pagamento se nao existirem."""
    for col in ("data_com", "data_pagamento"):
        try:
            conn.execute(f"ALTER TABLE dividendos ADD COLUMN {col} DATE")
        except sqlite3.OperationalError:
            pass
    # Remove UNIQUE antigo e recria tabela com UNIQUE melhor
    try:
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE name='dividendos' AND sql LIKE '%UNIQUE%'")
        row = cursor.fetchone()
        if row and "UNIQUE(ativo, data_ex, tipo)" in row[0]:
            conn.executescript("""
                CREATE TABLE dividendos_nova (
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
                );
                INSERT INTO dividendos_nova (id, ativo, tipo, data_ex, data_aprovacao, valor, tipo_acao, preco_fechamento, atualizado_em)
                    SELECT id, ativo, tipo, data_ex, data_aprovacao, valor, tipo_acao, preco_fechamento, atualizado_em FROM dividendos;
                DROP TABLE dividendos;
                ALTER TABLE dividendos_nova RENAME TO dividendos;
                CREATE INDEX IF NOT EXISTS idx_dividendos_ativo ON dividendos(ativo);
                CREATE INDEX IF NOT EXISTS idx_dividendos_data_com ON dividendos(data_com);
            """)
    except sqlite3.OperationalError:
        pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS instrumentos_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    cod_put TEXT NOT NULL,
    cod_call TEXT NOT NULL,
    vencimento DATE NOT NULL,
    tipo_opcao TEXT NOT NULL,
    strike REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parametros_operacionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT UNIQUE NOT NULL,
    valor TEXT NOT NULL,
    estrategia TEXT NOT NULL,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS oportunidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrumento_id INTEGER NOT NULL,
    preco_ativo REAL NOT NULL,
    strike REAL NOT NULL,
    dias INTEGER NOT NULL,
    cdi_periodo REAL NOT NULL,
    custo_sbth REAL NOT NULL DEFAULT 0,
    pct_ganho_sbth REAL NOT NULL DEFAULT 0,
    pct_cdi_sbth REAL NOT NULL DEFAULT 0,
    custo_box REAL NOT NULL DEFAULT 0,
    pct_ganho_box REAL NOT NULL DEFAULT 0,
    pct_cdi_box REAL NOT NULL DEFAULT 0,
    classificacao TEXT NOT NULL,
    operacao TEXT NOT NULL,
    snapshot_mercado TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instrumento_id) REFERENCES instrumentos_base(id)
);

CREATE TABLE IF NOT EXISTS estruturas_operacionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    oportunidade_id INTEGER,
    tipo TEXT NOT NULL,
    coefic_alvo REAL NOT NULL,
    coefic_mercado REAL NOT NULL,
    taxa_ganho REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (oportunidade_id) REFERENCES oportunidades(id)
);

CREATE TABLE IF NOT EXISTS pernas_operacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estrutura_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    lado TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    profundidade INTEGER NOT NULL,
    ordem INTEGER NOT NULL,
    FOREIGN KEY (estrutura_id) REFERENCES estruturas_operacionais(id)
);

CREATE TABLE IF NOT EXISTS dividendos (
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
);

CREATE INDEX IF NOT EXISTS idx_instrumentos_ativo ON instrumentos_base(ativo);
CREATE INDEX IF NOT EXISTS idx_instrumentos_vencimento ON instrumentos_base(vencimento);
CREATE INDEX IF NOT EXISTS idx_oportunidades_instrumento ON oportunidades(instrumento_id);
CREATE INDEX IF NOT EXISTS idx_estruturas_oportunidade ON estruturas_operacionais(oportunidade_id);
CREATE INDEX IF NOT EXISTS idx_pernas_estrutura ON pernas_operacao(estrutura_id);
"""
