# Database

Módulo de infraestrutura de banco de dados SQLite. Gerencia conexão (pool thread-local),
schema (DDL), migrações automáticas e seeding inicial de parâmetros. É o ponto único
de acesso ao banco para todo o sistema.

## Contrato (Requisitos)

### `get_db_path() -> Path`
**Garante:**
1. Retorna `%APPDATA%/Spreadhunter/spreadhunter.db`.
2. Se o arquivo não existe, tenta migrar de `config/spreadhunter.db` (legado) via `_migrar_banco_legado()`.
3. Cria o diretório pai se necessário.

### `get_connection(db_path=None) -> sqlite3.Connection`
**Garante:**
1. Pool thread-local: cada thread tem sua própria conexão, keyed por `md5(path)[:8]`.
2. Se a conexão existe e `SELECT 1` funciona, reutiliza.
3. Se `ProgrammingError` (conexão fechada), cria nova.
4. Configurações: `row_factory=sqlite3.Row`, `journal_mode=WAL`, `synchronous=NORMAL`, `cache_size=-8000` (8MB), `temp_store=MEMORY`, `foreign_keys=ON`.
5. `check_same_thread=False` — conexões podem ser usadas em threads diferentes da que as criou.

### `init_db(db_path=None) -> sqlite3.Connection`
**Garante:**
1. Executa `SCHEMA` — cria todas as tabelas se não existirem.
2. Roda migrações em sequência:
   - `_migrar_dividendos(conn)` — adiciona colunas `data_com`, `data_pagamento`, recria UNIQUE.
   - `_migrar_strike_column(conn)` — adiciona coluna `strike` em `instrumentos_base`.
   - `_seed_parametros_colar(conn)` — popula `parametros_operacionais` do JSON + fallbacks hardcoded.
   - `_migrar_fonte_market_data(conn)` — converte valores `0`/`1` → `"profit"`/`"openfast"`.
   - `_migrar_feriados_b3(conn)` — popula 40 feriados iniciais se tabela vazia.
   - `_migrar_calendario_resultados(conn)` — cria tabela `calendario_resultados`.
   - `_migrar_historico_simulacoes(conn)` — cria `historico_simulacoes` + ~50 colunas.
3. `conn.commit()` ao final.

### SCHEMA (string SQL)
**Garante:**
1. 14 tabelas: `instrumentos_base`, `parametros_operacionais`, `oportunidades`, `estruturas_operacionais`, `pernas_operacao`, `dividendos`, `feriados_b3`, `mpp_cache_opcoesnet`, `mpp_score_estrutural`, `mpp_box_score`, `mre_recomendacao`, `mpp_snapshot`, `mpp_historico_distorcoes`, `mpp_spread_history`, `taxas_aluguel`, `calendario_resultados`, `workspace_snapshots`, `historico_simulacoes`.
2. Índices: `idx_instrumentos_ativo`, `idx_instrumentos_vencimento`, `idx_oportunidades_instrumento`, `idx_estruturas_oportunidade`, `idx_pernas_estrutura`, `idx_feriados_b3_data`, `idx_mpp_box_score`, `idx_mpp_spread_history_codigo`, `idx_mpp_spread_history_data`, `idx_taxas_aluguel_ativo_data`, `idx_calendario_resultados_ativo`, `idx_calendario_resultados_data`, `idx_workspace_snapshots_nome`, `idx_historico_simulacoes_chassi`, `idx_historico_simulacoes_ativo`, `idx_historico_simulacoes_data`.

### `_seed_parametros_colar(conn)`
**Garante:**
1. Primeiro tenta carregar de `config/parametros_default.json` (via `_MEIPASS` ou path relativo).
2. Se falhar ou arquivo não existir, usa lista hardcoded de ~136 parâmetros divididos em:
   - `params` (54 itens): COLAR, COLLAR_CALENDARIO, GERAL, IMPORTACAO, BOX_4P, TELEGRAM, SOM, VENDA_COBERTA, SBTH_VENDIDA, BOX, BOX_SINTETICO, RATIOS_OTIMIZADOS, PROTECAO_CAUDA, TAXA_COMPRADA, VENDIDAS, PUT_RATIO.
   - `mpp_params` (28 itens): MPP (Motor de Priorização de Pescaria).
   - `perf_params` (16 itens): PERFORMANCE, GERAL, BOX_4P.
3. `INSERT OR IGNORE` — não sobrescreve parâmetros já existentes.

### `_migrar_dividendos(conn)`
**Garante:**
1. Adiciona colunas `data_com` e `data_pagamento` se ausentes.
2. Se o UNIQUE antigo for `(ativo, data_ex, tipo)`, recria tabela com novo UNIQUE `(ativo, data_com, tipo, data_pagamento)`.
3. Transação com rollback em caso de erro.

### `_migrar_fonte_market_data(conn)`
**Garante:**
1. Converte `fonte_market_data` de `"0"/"1"` (formato antigo) para `"profit"/"openfast"`.
2. Só age se o valor atual for `"0"` ou `"1"`.

### `_migrar_feriados_b3(conn)`
**Garante:**
1. Popula 40 feriados (2024-2026) se a tabela estiver vazia.
2. `INSERT OR IGNORE` — idempotente.

### `_migrar_historico_simulacoes(conn)`
**Garante:**
1. Cria tabela `historico_simulacoes` com 20 colunas base + índices.
2. Tenta adicionar ~50 colunas adicionais via `ALTER TABLE ADD COLUMN` com `try/except` (idempotente).
   POSSÍVEL PROBLEMA DE ESCALA: 50+ ALTER TABLE em todo `init_db()` — se a tabela já tem todas as colunas,
   são 50 exceções silenciosas por inicialização. Performance não é crítica (só no bootstrap), mas é ruidoso.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| hashlib | `md5` | Key do pool thread-local |
| json | `load` | Leitura de `parametros_default.json` |
| logging | `getLogger` | Logs de migração |
| os | `environ` | `%APPDATA%` |
| shutil | `copy2` | Migração de banco legado |
| sqlite3 | `connect`, `Row`, `ProgrammingError`, `OperationalError` | Tudo |
| sys | `argv`, `_MEIPASS` | Paths |
| threading | `local` | Pool thread-local |
| pathlib | `Path` | Manipulação de paths |

**É dependência de:**
- 33 call sites em produção + testes
- `bootstrap.py` — `init_db()`
- `repositories.py`, `workspace_repository.py` — `get_connection()`
- `importflash.py` — `get_db_path()`
- `main_window.py`, `monitor_worker.py`, `calculadoras_dialog.py`, `colar_calendario_dialog.py`, `estudos_calendario_dialog.py`, `historico_simulacoes_dialog.py`, `sensibilidade_mercado_widget.py` — `get_db_path()` ou `get_connection()`
- `mpp_use_case.py`, `calculadora_colar_calendario.py` — `get_connection()`
- `scripts/simular_protecao_cauda.py`, `scripts/verificar_integridade_params.py`
- Todos os arquivos de teste — `init_db()`

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 765 |
| Arquivo | `src/infrastructure/persistence/database.py` |
| Última modificação | 2026-07-24 |

## Notas
- 2026-07-24: última modificação (adição de migrações/campos no `historico_simulacoes`).
- 2026-07-23: dois commits no mesmo dia (refatoração de migrações).
- `_migrar_historico_simulacoes` tem ~50 `ALTER TABLE ADD COLUMN` com `try/except` — funciona mas é frágil; um erro real de schema seria silenciado.
- `SCHEMA` e `_migrar_historico_simulacoes` mantêm definições duplicadas de colunas — se o schema base mudar, a migração pode ficar inconsistente.
- Pool thread-local com `md5` do path — duas threads com o mesmo `db_path` compartilham conexão (design intencional).
