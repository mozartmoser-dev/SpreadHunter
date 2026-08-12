# FeriadoB3Repository

Repositório para feriados da B3 (tabela `feriados_b3`). Persiste feriados obtidos da Brasil API com upsert por data. Suporta consultas por ano e limpeza seletiva.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `save_batch(feriados: list[dict]) -> int`
**Garante:**
1. `executemany` com `ON CONFLICT(data) DO UPDATE`.
2. Colunas: `data`, `nome`, `tipo`, `fonte`.
3. No update, atualiza `nome`, `tipo`, `fonte`, `atualizado_em=CURRENT_TIMESTAMP`.

### `get_all() -> list[dict]`
**Garante:**
1. `SELECT * ORDER BY data`.

### `get_by_ano(ano: int) -> list[dict]`
**Garante:**
1. `WHERE data >= 'YYYY-01-01' AND data <= 'YYYY-12-31'`.

### `get_anos_disponiveis() -> list[int]`
**Garante:**
1. `SELECT DISTINCT CAST(substr(data, 1, 4) AS INTEGER) AS ano ORDER BY ano`.

### `delete_by_ano(ano: int) -> int`
**Garante:**
1. `DELETE WHERE data >= 'YYYY-01-01' AND data <= 'YYYY-12-31'`.

### `delete_all() -> int`
**Garante:**
1. `DELETE FROM feriados_b3`.

### `replace_feriados_ano(ano: int, feriados: list[dict]) -> int`
**Garante:**
1. DELETE + INSERT na **mesma transação** com rollback em caso de falha.
2. DELETE `WHERE data >= 'YYYY-01-01' AND data <= 'YYYY-12-31'`.
3. Se `feriados` não vazio, `executemany` com `ON CONFLICT(data) DO UPDATE`.
4. Substitui atomicamente o par `delete_by_ano` + `save_batch`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 74 (linhas 732-805 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`FeriadoB3Repository`) |

## Notas

- 2026-08-06 — mesma data.
- Usa `dict` como entidade (sem classe de domínio).
- Upsert por `data` — cada data só pode ter um registro. Se Brasil API e provider manual (9 de Julho) conflitarem, o último a gravar vence.
