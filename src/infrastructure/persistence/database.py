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
    _migrar_feriados_b3(conn)
    conn.commit()
    return conn


def _seed_parametros_colar(conn):
    params = [
        ("premio_risco_colar", "1.05", "COLAR", "Premio risco Colar (x CDI)"),
        ("colar_dist_max_pct", "0.15", "COLAR", "Distancia maxima do strike (%)"),
        ("calendario_strike_diff_pct", "0.03", "COLLAR_CALENDARIO", "Max diff % entre strikes call e put"),
        ("premio_risco_colar_calendario", "1.2", "COLLAR_CALENDARIO", "Premio risco Collar Calendario (x CDI)"),
        ("calendario_call_otm_max", "0.04", "COLLAR_CALENDARIO", "Max OTM da call (% do spot)"),
        ("taxa_emolumento_pct", "0.00025", "GERAL", "Taxa de emolumento B3 (% do financeiro)"),
        ("taxa_liquidacao_pct", "0.000275", "GERAL", "Taxa de liquidacao B3 (% do financeiro)"),
        ("colar_qul_min_put", "100", "COLAR", "Qtd minima negociada (QUL) para PUT"),
        ("colar_qul_min_call", "100", "COLAR", "Qtd minima negociada (QUL) para CALL"),
        ("colar_risco_baixo_vov_min", "1000", "COLAR", "VOV/VOC mínimo para risco baixo de despernamento"),
        ("elegibilidade_strike_max_pct", "0.70", "BOX_SINTETICO", "Strike máximo % do spot para elegibilidade de pescaria"),
        ("dte_call_min", "29", "COLLAR_CALENDARIO", "DTE mínimo para call no collar calendário"),
        ("dte_call_max", "60", "COLLAR_CALENDARIO", "DTE máximo para call no collar calendário"),
        ("dte_extra_min", "30", "COLLAR_CALENDARIO", "Spread DTE mínimo entre put e call"),
        ("dte_extra_max", "90", "COLLAR_CALENDARIO", "Spread DTE máximo entre put e call"),
        ("dte_total_max", "120", "COLLAR_CALENDARIO", "DTE máximo total para qualquer perna"),
    ]
    for chave, valor, estrategia, descricao in params:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO parametros_operacionais (chave, valor, estrategia, descricao) VALUES (?, ?, ?, ?)",
                (chave, valor, estrategia, descricao),
            )
        except sqlite3.OperationalError:
            pass


def _migrar_feriados_b3(conn):
    """Popula feriados_b3 com dados iniciais se vazia."""
    try:
        count = conn.execute("SELECT COUNT(*) FROM feriados_b3").fetchone()[0]
        if count == 0:
            feriados_iniciais = [
                ("2024-01-01", "Confraternização Universal", "nacional"),
                ("2024-02-12", "Carnaval", "nacional"),
                ("2024-02-13", "Carnaval", "nacional"),
                ("2024-03-29", "Sexta-feira Santa", "nacional"),
                ("2024-04-21", "Tiradentes", "nacional"),
                ("2024-05-01", "Dia do Trabalho", "nacional"),
                ("2024-05-30", "Corpus Christi", "nacional"),
                ("2024-07-09", "Revolução Constitucionalista", "estadual_sp"),
                ("2024-09-07", "Independência do Brasil", "nacional"),
                ("2024-10-12", "Nossa Sra. Aparecida", "nacional"),
                ("2024-11-02", "Finados", "nacional"),
                ("2024-11-15", "Proclamação da República", "nacional"),
                ("2024-11-20", "Consciência Negra", "nacional"),
                ("2024-12-25", "Natal", "nacional"),
                ("2025-01-01", "Confraternização Universal", "nacional"),
                ("2025-03-04", "Carnaval", "nacional"),
                ("2025-04-18", "Sexta-feira Santa", "nacional"),
                ("2025-04-21", "Tiradentes", "nacional"),
                ("2025-05-01", "Dia do Trabalho", "nacional"),
                ("2025-06-19", "Corpus Christi", "nacional"),
                ("2025-07-09", "Revolução Constitucionalista", "estadual_sp"),
                ("2025-09-07", "Independência do Brasil", "nacional"),
                ("2025-10-12", "Nossa Sra. Aparecida", "nacional"),
                ("2025-11-02", "Finados", "nacional"),
                ("2025-11-15", "Proclamação da República", "nacional"),
                ("2025-11-20", "Consciência Negra", "nacional"),
                ("2025-12-25", "Natal", "nacional"),
                ("2026-01-01", "Confraternização Universal", "nacional"),
                ("2026-02-16", "Carnaval", "nacional"),
                ("2026-02-17", "Carnaval", "nacional"),
                ("2026-04-03", "Sexta-feira Santa", "nacional"),
                ("2026-04-21", "Tiradentes", "nacional"),
                ("2026-05-01", "Dia do Trabalho", "nacional"),
                ("2026-06-04", "Corpus Christi", "nacional"),
                ("2026-07-09", "Revolução Constitucionalista", "estadual_sp"),
                ("2026-09-07", "Independência do Brasil", "nacional"),
                ("2026-10-12", "Nossa Sra. Aparecida", "nacional"),
                ("2026-11-02", "Finados", "nacional"),
                ("2026-11-15", "Proclamação da República", "nacional"),
                ("2026-11-20", "Consciência Negra", "nacional"),
                ("2026-12-25", "Natal", "nacional"),
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO feriados_b3 (data, nome, tipo) VALUES (?, ?, ?)",
                feriados_iniciais,
            )
    except Exception:
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

CREATE TABLE IF NOT EXISTS feriados_b3 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data DATE NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    tipo TEXT DEFAULT 'nacional',
    fonte TEXT DEFAULT 'brasilapi',
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_instrumentos_ativo ON instrumentos_base(ativo);
CREATE INDEX IF NOT EXISTS idx_instrumentos_vencimento ON instrumentos_base(vencimento);
CREATE INDEX IF NOT EXISTS idx_oportunidades_instrumento ON oportunidades(instrumento_id);
CREATE INDEX IF NOT EXISTS idx_estruturas_oportunidade ON estruturas_operacionais(oportunidade_id);
CREATE INDEX IF NOT EXISTS idx_pernas_estrutura ON pernas_operacao(estrutura_id);
CREATE INDEX IF NOT EXISTS idx_feriados_b3_data ON feriados_b3(data);
"""
