import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import threading
from pathlib import Path

DB_NAME = "spreadhunter.db"

_db_local = threading.local()
_logger = logging.getLogger(__name__)


def _get_appdata_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / ".local/share")) / "Spreadhunter"


def get_db_path() -> Path:
    appdata_dir = _get_appdata_dir()
    db_path = appdata_dir / DB_NAME
    if not db_path.exists():
        _migrar_banco_legado(db_path)
    return db_path


def _migrar_banco_legado(novo_path: Path) -> None:
    """Copia banco existente de config/ para %APPDATA%/Spreadhunter/ na 1ª execução."""
    candidatos = [
        Path(__file__).resolve().parent.parent.parent.parent / "config" / DB_NAME,
        Path(sys.argv[0]).parent / "config" / DB_NAME if hasattr(sys, "argv") and sys.argv else None,
    ]
    for velho in candidatos:
        if velho and velho.exists():
            try:
                novo_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(velho), str(novo_path))
                _logger.info("Banco migrado de %s para %s", velho, novo_path)
            except Exception as e:
                _logger.warning("Falha ao migrar banco de %s: %s", velho, e)
            return
    novo_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    local_key = "db_" + hashlib.md5(str(path).encode()).hexdigest()[:8]
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
    _migrar_strike_column(conn)
    _seed_parametros_colar(conn)
    _migrar_fonte_market_data(conn)
    _migrar_feriados_b3(conn)
    _migrar_calendario_resultados(conn)
    _migrar_historico_simulacoes(conn)
    conn.commit()
    return conn


def _migrar_historico_simulacoes(conn):
    """Cria tabela historico_simulacoes se nao existir (Fase Otimizado)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historico_simulacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_chassi TEXT NOT NULL,
            estagio TEXT NOT NULL,
            ativo TEXT NOT NULL,
            preco_ativo REAL NOT NULL,
            strike_call REAL NOT NULL,
            strike_put REAL NOT NULL,
            dte_original INTEGER NOT NULL,
            iv_call REAL NOT NULL,
            ratio_call REAL NOT NULL,
            ratio_put REAL NOT NULL,
            pnl_cauda_esq REAL NOT NULL,
            pnl_cauda_dir REAL NOT NULL,
            be_esq REAL,
            be_dir REAL,
            pct_cdi REAL NOT NULL,
            detectado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_historico_simulacoes_chassi ON historico_simulacoes(id_chassi)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_historico_simulacoes_ativo ON historico_simulacoes(ativo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_historico_simulacoes_data ON historico_simulacoes(detectado_em)")


def _seed_parametros_colar(conn):
    _base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent.parent))
    json_path = _base / "config" / "parametros_default.json"
    if json_path.is_file():
        try:
            with open(str(json_path), "r", encoding="utf-8") as f:
                data = json.load(f)
            for p in data.get("parametros", []):
                conn.execute(
                    "INSERT OR IGNORE INTO parametros_operacionais (chave, valor, estrategia, descricao) VALUES (?, ?, ?, ?)",
                    (p["chave"], p["valor"], p.get("estrategia", ""), p.get("descricao", "")),
                )
            return
        except Exception:
            pass
    params = [
        ("premio_risco_colar", "0.7", "COLAR", "Premio risco Colar (x CDI)"),
        ("colar_dist_max_pct", "0.15", "COLAR", "Distancia maxima do strike (%)"),
        ("calendario_strike_diff_max", "1", "COLLAR_CALENDARIO", "Max strikes de diferenca entre call e put"),
        ("premio_risco_colar_calendario", "0.9", "COLLAR_CALENDARIO", "Premio risco Collar Calendario (x CDI)"),
        ("calendario_call_otm_max", "0.15", "COLLAR_CALENDARIO", "Max OTM da call (% do spot)"),
        ("taxa_emolumento_pct", "0.00025", "GERAL", "Taxa de emolumento B3 (% do financeiro)"),
        ("taxa_liquidacao_pct", "0.000275", "GERAL", "Taxa de liquidacao B3 (% do financeiro)"),
        ("colar_qtd_ativo", "100", "COLAR", "Qtd compra ativo"),
        ("colar_prof_ativo", "1", "COLAR", "Profundidade book ativo"),
        ("colar_qtd_call", "100", "COLAR", "Qtd venda CALL"),
        ("colar_prof_call", "-1", "COLAR", "Profundidade book Call"),
        ("colar_qtd_put", "100", "COLAR", "Qtd compra PUT"),
        ("colar_prof_put", "-1", "COLAR", "Profundidade book Put"),
        ("calendario_qtd_ativo", "100", "COLLAR_CALENDARIO", "Qtd compra ativo"),
        ("calendario_prof_ativo", "1", "COLLAR_CALENDARIO", "Profundidade book ativo"),
        ("calendario_qtd_call", "100", "COLLAR_CALENDARIO", "Qtd venda CALL"),
        ("calendario_prof_call", "-1", "COLLAR_CALENDARIO", "Profundidade book Call"),
        ("calendario_qtd_put", "100", "COLLAR_CALENDARIO", "Qtd compra PUT"),
        ("calendario_prof_put", "-1", "COLLAR_CALENDARIO", "Profundidade book Put"),
        ("colar_qul_min_put", "100", "COLAR", "Qtd minima negociada (QUL) para PUT"),
        ("colar_qul_min_call", "100", "COLAR", "Qtd minima negociada (QUL) para CALL"),
        ("colar_risco_baixo_vov_min", "1000", "COLAR", "VOV/VOC mínimo para risco baixo de despernamento"),
        ("ranking_peso_colar_pop", "3.0", "COLAR", "Peso da Pop no Score do Colar Protetivo"),
        ("ranking_peso_colar_cdi", "2.0", "COLAR", "Peso do % CDI no Score do Colar Protetivo"),
        ("ranking_peso_colar_risco", "1.0", "COLAR", "Peso do risco de leilão (inverso) no Score do Colar Protetivo"),
        ("taxa_ir_pct", "0.15", "GERAL", "Aliquota de IR sobre lucro em operacoes (15% swing trade)"),
        ("rtd_refresh_timeout_ms", "5000", "GERAL", "Timeout do RTD RefreshData em ms (0 = sem timeout)"),
        ("fonte_market_data", "openfast", "GERAL", "Fonte de market data (profit=Profit RTD via COM, openfast=Open Fast Socket TCP, mock=Dados simulados p/ teste)"),
        ("openfast_send_delay_ms", "2", "GERAL", "Delay entre comandos SQT (ms). 0 = delay minimo (1ms)"),
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
        ("ranking_peso_theta", "3.0", "COLLAR_CALENDARIO", "Peso do theta líquido no ranking (Score)"),
        ("ranking_peso_cdi", "2.0", "COLLAR_CALENDARIO", "Peso do % CDI no ranking (Score)"),
        ("ranking_peso_sigma", "2.0", "COLLAR_CALENDARIO", "Peso da folga sigma (distância strikes) no ranking (Score)"),
        ("ranking_peso_credito", "1.0", "COLLAR_CALENDARIO", "Peso do crédito líquido no ranking (Score)"),
        ("ranking_peso_liquidez", "0.5", "COLLAR_CALENDARIO", "Peso da liquidez no ranking (Score)"),
        ("ranking_peso_iv_rank", "25.0", "COLLAR_CALENDARIO", "Peso do IV Rank no Score IV (0-100)"),
        ("ranking_peso_dist_strike", "25.0", "COLLAR_CALENDARIO", "Peso da Dist Strike/Custo no Score IV"),
        ("ranking_peso_theta_margin", "25.0", "COLLAR_CALENDARIO", "Peso do Theta/Margin no Score IV"),
        ("ranking_peso_vega", "10.0", "COLLAR_CALENDARIO", "Peso do Vega líquido no Score IV"),
        ("ranking_peso_liquidez_iv", "10.0", "COLLAR_CALENDARIO", "Peso da Liquidez no Score IV"),
        ("ranking_peso_risco_max", "5.0", "COLLAR_CALENDARIO", "Peso do Risco Máx (invertido) no Score IV"),
    ]
    mpp_params = [
        ("mpp_habilitado",           "1",    "MPP", "Habilitar Motor de Priorizacao de Pescaria"),
        ("mpp_peso_oi",              "0.15", "MPP", "Peso concentracao OI no score estrutural"),
        ("mpp_peso_volume",          "0.10", "MPP", "Peso baixo volume no score estrutural"),
        ("mpp_peso_curvatura_iv",    "0.10", "MPP", "Peso curvatura IV no score estrutural"),
        ("mpp_peso_paridade",        "0.25", "MPP", "Peso erro de paridade no score instantaneo"),
        ("mpp_peso_spread",          "0.20", "MPP", "Peso spread medio no score instantaneo"),
        ("mpp_peso_profundidade",    "0.10", "MPP", "Peso profundidade no score instantaneo"),
        ("mpp_peso_imbalance",       "0.0",  "MPP", "Peso book imbalance no score instantaneo (descontinuado)"),
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
        ("taxa_aluguel_habilitado", "1", "GERAL", "Habilitar coleta de taxas de aluguel (InvestSite)"),
        ("investsite_timeout_ms", "10000", "GERAL", "Timeout das requisicoes HTTP ao InvestSite (ms)"),
        ("investsite_delay_ms", "500", "GERAL", "Delay entre requisicoes ao InvestSite (ms)"),
        ("som_arquivo", "", "SOM", "Arquivo de som .wav para notificacoes (vazio = beep padrao)"),
        ("som_volume", "100", "SOM", "Volume do som de notificacao (0-100)"),
        ("som_arquivo_vendidas", "", "SOM", "Arquivo de som .wav para notificacoes VENDIDAS (vazio = beep padrao)"),
        ("som_volume_vendidas", "100", "SOM", "Volume do som de notificacao VENDIDAS (0-100)"),
        ("som_arquivo_coberta", "", "SOM", "Arquivo de som .wav para notificacoes VENDA COBERTA (vazio = beep padrao)"),
        ("som_volume_coberta", "100", "SOM", "Volume do som de notificacao VENDA COBERTA (0-100)"),
        ("fonte_tamanho", "9", "GERAL", "Tamanho da fonte do sistema (8-16)"),
        ("venda_coberta_premio_risco", "1.08", "VENDA_COBERTA", "Premio risco minimo sobre CDI para Venda Coberta"),
        ("venda_coberta_lote_liquidez", "100", "VENDA_COBERTA", "Lote minimo de liquidez da CALL para Venda Coberta"),
        ("venda_coberta_dias_maximos", "30", "VENDA_COBERTA", "Dias maximos ate o vencimento para TAXA"),
        ("venda_coberta_dist_max_pct", "0.20", "VENDA_COBERTA", "Distancia maxima do strike abaixo do spot (%)"),
        ("sbth_vendida_dist_ativo", "1.20", "SBTH_VENDIDA", "Distancia minima strike/spot (x) para SBTH Vendida — filtro de entrada"),
        ("otimizado_desvios_sigma", "2.0", "COLLAR_CALENDARIO", "Desvios padrao para o range do otimizado"),
        ("otimizado_ratio_max", "1.40", "COLLAR_CALENDARIO", "Ratio maximo CALL:ativo permitido"),
        ("otimizado_ratio_put_min", "0.80", "COLLAR_CALENDARIO", "Ratio minimo da PUT permitido"),
        ("otimizado_ratio_put_step", "0.10", "COLLAR_CALENDARIO", "Passo de varredura dos ratios (LOTE/qtd_acao)"),
    ]
    for p in params + mpp_params + perf_params:
        conn.execute(
            "INSERT OR IGNORE INTO parametros_operacionais (chave, valor, estrategia, descricao) VALUES (?, ?, ?, ?)",
            p,
        )


def _migrar_strike_column(conn):
    """Adiciona coluna strike em instrumentos_base se nao existir."""
    try:
        conn.execute("ALTER TABLE instrumentos_base ADD COLUMN strike REAL")
    except sqlite3.OperationalError:
        pass


def _migrar_fonte_market_data(conn):
    """Converte fonte_market_data de 0/1 para profit/openfast."""
    try:
        row = conn.execute(
            "SELECT valor FROM parametros_operacionais WHERE chave = 'fonte_market_data'"
        ).fetchone()
        if row and row[0] in ("0", "1"):
            novo = "profit" if row[0] == "0" else "openfast"
            conn.execute(
                "UPDATE parametros_operacionais SET valor = ? WHERE chave = 'fonte_market_data'",
                (novo,),
            )
            _logger.info("fonte_market_data migrado: %s → %s", row[0], novo)
    except Exception:
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


def _migrar_calendario_resultados(conn):
    """Cria tabela calendario_resultados se nao existir."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendario_resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ativo TEXT NOT NULL,
            cnpj TEXT,
            nome_empresa TEXT,
            data_publicacao DATE NOT NULL,
            trimestre_referencia TEXT,
            tipo_documento TEXT DEFAULT 'ITR',
            tipo_evento TEXT DEFAULT 'previsto',
            fonte TEXT DEFAULT 'webwallet',
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ativo, data_publicacao, trimestre_referencia, tipo_evento)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calendario_resultados_ativo ON calendario_resultados(ativo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calendario_resultados_data ON calendario_resultados(data_publicacao)")


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

CREATE TABLE IF NOT EXISTS taxas_aluguel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    data DATE NOT NULL,
    taxa_atual REAL NOT NULL,
    taxa_7d REAL NOT NULL,
    taxa_28d REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ativo, data)
);

CREATE INDEX IF NOT EXISTS idx_taxas_aluguel_ativo_data ON taxas_aluguel(ativo, data);

CREATE TABLE IF NOT EXISTS calendario_resultados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT NOT NULL,
    cnpj TEXT,
    nome_empresa TEXT,
    data_publicacao DATE NOT NULL,
    trimestre_referencia TEXT,
    tipo_documento TEXT DEFAULT 'ITR',
    tipo_evento TEXT DEFAULT 'previsto',
    fonte TEXT DEFAULT 'webwallet',
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ativo, data_publicacao, trimestre_referencia, tipo_evento)
);

CREATE INDEX IF NOT EXISTS idx_calendario_resultados_ativo ON calendario_resultados(ativo);
CREATE INDEX IF NOT EXISTS idx_calendario_resultados_data ON calendario_resultados(data_publicacao);

CREATE TABLE IF NOT EXISTS workspace_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_system INTEGER NOT NULL DEFAULT 0,
    app_version TEXT NOT NULL,
    parametros_json TEXT NOT NULL DEFAULT '{}',
    workspace_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_workspace_snapshots_nome ON workspace_snapshots(nome);

CREATE TABLE IF NOT EXISTS historico_simulacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_chassi TEXT NOT NULL,
    estagio TEXT NOT NULL,
    ativo TEXT NOT NULL,
    preco_ativo REAL NOT NULL,
    strike_call REAL NOT NULL,
    strike_put REAL NOT NULL,
    dte_original INTEGER NOT NULL,
    iv_call REAL NOT NULL,
    ratio_call REAL NOT NULL,
    ratio_put REAL NOT NULL,
    pnl_cauda_esq REAL NOT NULL,
    pnl_cauda_dir REAL NOT NULL,
    be_esq REAL,
    be_dir REAL,
    pct_cdi REAL NOT NULL,
    detectado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_historico_simulacoes_chassi ON historico_simulacoes(id_chassi);
CREATE INDEX IF NOT EXISTS idx_historico_simulacoes_ativo ON historico_simulacoes(ativo);
CREATE INDEX IF NOT EXISTS idx_historico_simulacoes_data ON historico_simulacoes(detectado_em);
"""
