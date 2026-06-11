import sqlite3
import threading
from pathlib import Path

DB_NAME = "spreadhunter.db"

_db_local = threading.local()


def get_db_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "config" / DB_NAME


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    local_key = str(path)
    if hasattr(_db_local, local_key):
        conn = getattr(_db_local, local_key)
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA foreign_keys=ON")
    setattr(_db_local, local_key, conn)
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
        ("premio_risco_colar", "0.7", "COLAR", "Premio risco Colar (x CDI)"),
        ("colar_dist_max_pct", "0.15", "COLAR", "Distancia maxima do strike (%)"),
        ("calendario_strike_diff_max", "1", "COLLAR_CALENDARIO", "Max strikes de diferenca entre call e put"),
        ("premio_risco_colar_calendario", "0.9", "COLLAR_CALENDARIO", "Premio risco Collar Calendario (x CDI)"),
        ("calendario_call_otm_max", "0.15", "COLLAR_CALENDARIO", "Max OTM da call (% do spot)"),
        ("taxa_emolumento_pct", "0.00025", "GERAL", "Taxa de emolumento B3 (% do financeiro)"),
        ("taxa_liquidacao_pct", "0.000275", "GERAL", "Taxa de liquidacao B3 (% do financeiro)"),
        ("colar_qul_min_put", "100", "COLAR", "Qtd minima negociada (QUL) para PUT"),
        ("colar_qul_min_call", "100", "COLAR", "Qtd minima negociada (QUL) para CALL"),
        ("colar_risco_baixo_vov_min", "1000", "COLAR", "VOV/VOC mínimo para risco baixo de despernamento"),
        ("taxa_ir_pct", "0.15", "GERAL", "Aliquota de IR sobre lucro em operacoes (15% swing trade)"),
        ("rtd_refresh_timeout_ms", "5000", "GERAL", "Timeout do RTD RefreshData em ms (0 = sem timeout)"),
        ("elegibilidade_strike_max_pct", "0.70", "BOX_SINTETICO", "Strike máximo % do spot para elegibilidade de pescaria"),
        ("dte_call_min", "25", "COLLAR_CALENDARIO", "DTE mínimo para call no collar calendário"),
        ("dte_call_max", "60", "COLLAR_CALENDARIO", "DTE máximo para call no collar calendário"),
        ("dte_extra_min", "30", "COLLAR_CALENDARIO", "Spread DTE mínimo entre put e call"),
        ("dte_extra_max", "120", "COLLAR_CALENDARIO", "Spread DTE máximo entre put e call"),
        ("dte_total_max", "180", "COLLAR_CALENDARIO", "DTE máximo total para qualquer perna"),
        ("import_max_months", "9", "IMPORTACAO", "Meses a frente da data para importar series"),
        ("white_list_box4p", "", "BOX_4P", "Whitelist de ativos para Box 4P"),
        ("limiar_classificacao_calendario", "0.15", "COLLAR_CALENDARIO", "Limiar de classificacao (% do spread entre strikes)"),
        ("be_search_range_mult", "0.15", "COLLAR_CALENDARIO", "Margem +/- busca breakeven (ex: 0.15 = 0.85x a 1.15x)"),
        ("white_list_colar_calendario", "", "COLLAR_CALENDARIO", "Whitelist de ativos para Collar Calendario"),
        ("white_list_colar", "", "COLAR", "Whitelist de ativos para Colar Protetivo"),
        ("telegram_cleanup_timeout", "300", "TELEGRAM", "Timeout de limpeza do historico Telegram (segundos)"),
    ]
    mpp_params = [
        ("mpp_habilitado",           "1",    "MPP", "Habilitar Motor de Priorizacao de Pescaria"),
        ("mpp_peso_oi",              "0.15", "MPP", "Peso concentracao OI no score estrutural"),
        ("mpp_peso_volume",          "0.10", "MPP", "Peso baixo volume no score estrutural"),
        ("mpp_peso_curvatura_iv",    "0.10", "MPP", "Peso curvatura IV no score estrutural"),
        ("mpp_peso_paridade",        "0.25", "MPP", "Peso erro de paridade no score instantaneo"),
        ("mpp_peso_spread",          "0.20", "MPP", "Peso spread medio no score instantaneo"),
        ("mpp_peso_profundidade",    "0.10", "MPP", "Peso profundidade no score instantaneo"),
        ("mpp_peso_imbalance",       "0.05", "MPP", "Peso book imbalance no score instantaneo"),
        ("mpp_peso_spread_anomalia", "0.05", "MPP", "Peso anomalia de spread no score instantaneo"),
        ("mpp_spread_history_len",   "200",  "MPP", "Tamanho do deque de historico de spread"),
        ("mpp_spread_min_anomalia",  "0.02", "MPP", "Spread minimo para considerar anomalia (2%)"),
        ("mpp_curvatura_normalizador", "0.10", "MPP", "Denominador de normalizacao da curvatura IV"),
        ("mpp_oi_peso_absoluto",     "0.40", "MPP", "Peso do tamanho absoluto OI no score OI"),
        ("mpp_oi_peso_concentracao", "0.60", "MPP", "Peso da concentracao relativa OI no score OI"),
        ("mpp_oi_cap_absoluto",      "10000","MPP", "Cap de OI absoluto para normalizacao"),
        ("mpp_dte_fator_min",        "0.60", "MPP", "Fator DTE minimo (para vencimentos extremos)"),
        ("mpp_dte_ideal_min",        "10",   "MPP", "DTE minimo da janela ideal"),
        ("mpp_dte_ideal_max",        "25",   "MPP", "DTE maximo da janela ideal"),
        ("mpp_instantaneo_interval", "4",    "MPP", "Ciclos entre calculos MPP instantaneos"),
        ("mpp_persistencia_max_mult","0.50", "MPP", "Multiplicador maximo da persistencia"),
        ("mpp_persistencia_divisor", "20",   "MPP", "Ciclos para atingir 1x de bonus de persistencia"),
        ("box_premio_risco",         "1.08", "MPP", "Premio risco minimo sobre CDI para pescaria de Box"),
        ("mpp_paridade_normalizador","0.10", "MPP", "Fator de normalizacao do erro de paridade do Box"),
        ("mpp_erro_paridade_limiar", "0.02", "MPP", "Limiar de erro de paridade para acumular persistencia"),
        ("mpp_peso_estrutural",      "0.35", "MPP", "Peso do score estrutural no score final"),
        ("mpp_peso_instantaneo",     "0.65", "MPP", "Peso do score instantaneo no score final"),
        ("mpp_bonus_max",            "0.15", "MPP", "Bonus maximo historico"),
        ("mpp_bonus_taxa",           "0.25", "MPP", "Taxa de conversao sucesso em bonus"),
        ("mre_lote_base",            "100",  "MRE", "Lote base para calculo de lote sugerido"),
        ("mre_profundidade_max_pct", "0.20", "MRE", "Maximo %% da profundidade a consumir"),
    ]
    perf_params = [
        ("perf_carga_inteligente", "1", "PERFORMANCE", "Habilitar carga inteligente"),
        ("perf_range_min", "-70", "PERFORMANCE", "Range minimo de strike (%)"),
        ("perf_range_max", "70", "PERFORMANCE", "Range maximo de strike (%)"),
        ("perf_limite_meses", "6", "PERFORMANCE", "Limite de meses (max) para registrar Onda 1"),
        ("perf_dias_minimos", "7", "PERFORMANCE", "Dias minimos ate o vencimento (min) para registrar Onda 1"),
        ("onda2_dte_min", "7", "PERFORMANCE", "DTE minimo para registrar Onda 2"),
        ("onda2_dte_max", "180", "PERFORMANCE", "DTE maximo para registrar Onda 2"),
        ("box_scan_interval", "5", "BOX_4P", "Ciclos entre varreduras de Box 4P"),
    ]
    params.extend(perf_params)
    params.extend(mpp_params)
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
            conn.execute("BEGIN TRANSACTION")
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
            conn.execute("COMMIT")
    except sqlite3.OperationalError:
        conn.execute("ROLLBACK")


SCHEMA = """
CREATE TABLE IF NOT EXISTS instrumentos_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    cod_put TEXT NOT NULL,
    cod_call TEXT NOT NULL,
    vencimento DATE NOT NULL,
    tipo_opcao TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS mpp_cache_opcoesnet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    opcao TEXT NOT NULL,
    strike REAL NOT NULL,
    tipo TEXT NOT NULL,
    vencimento DATE NOT NULL,
    oi INTEGER DEFAULT 0,
    volume_financeiro REAL DEFAULT 0,
    num_negocios INTEGER DEFAULT 0,
    iv REAL,
    delta REAL,
    gamma REAL,
    ultimo_preco REAL,
    mod TEXT,
    data_ref DATE NOT NULL,
    UNIQUE(ativo, opcao, data_ref)
);

CREATE TABLE IF NOT EXISTS mpp_score_estrutural (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    opcao TEXT NOT NULL,
    strike REAL NOT NULL,
    vencimento DATE NOT NULL,
    score_oi REAL DEFAULT 0,
    score_volume REAL DEFAULT 0,
    score_curvatura_iv REAL DEFAULT 0,
    score_estrutural REAL DEFAULT 0,
    data_ref DATE NOT NULL,
    UNIQUE(ativo, opcao, data_ref)
);

CREATE TABLE IF NOT EXISTS mpp_box_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    strike1 REAL NOT NULL,
    strike2 REAL NOT NULL,
    vencimento DATE NOT NULL,
    score_estrutural REAL DEFAULT 0,
    score_instantaneo REAL DEFAULT 0,
    score_final REAL DEFAULT 0,
    erro_paridade_box REAL,
    spread_medio REAL,
    profundidade_min REAL,
    persistencia_ciclos INTEGER DEFAULT 0,
    nivel_risco TEXT DEFAULT 'baixo',
    justificativa TEXT DEFAULT '',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mpp_box_score ON mpp_box_score(score_final DESC);

CREATE TABLE IF NOT EXISTS mre_recomendacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    strike1 REAL NOT NULL,
    strike2 REAL NOT NULL,
    vencimento DATE NOT NULL,
    score_box REAL DEFAULT 0,
    isca_recomendada TEXT,
    ip_isca REAL DEFAULT 0,
    lote_sugerido INTEGER DEFAULT 0,
    confianca_completar REAL DEFAULT 0,
    ganho_estimado REAL DEFAULT 0,
    custo_montagem REAL DEFAULT 0,
    relacao_custo_ganho REAL DEFAULT 0,
    nivel_recomendacao TEXT DEFAULT 'baixa',
    justificativa TEXT DEFAULT '',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mpp_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    strike1 REAL NOT NULL,
    strike2 REAL NOT NULL,
    vencimento DATE NOT NULL,
    score_final REAL DEFAULT 0,
    score_estrutural REAL DEFAULT 0,
    score_instantaneo REAL DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mpp_historico_distorcoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    strike1 REAL,
    strike2 REAL,
    data DATE NOT NULL,
    score_box REAL DEFAULT 0,
    box_encontrado INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mpp_spread_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL,
    spread_pct REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mpp_spread_history_codigo ON mpp_spread_history(codigo);
CREATE INDEX IF NOT EXISTS idx_mpp_spread_history_data ON mpp_spread_history(created_at);
"""
