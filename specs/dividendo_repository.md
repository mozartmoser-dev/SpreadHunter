# DividendoRepository

Repositório para dividendos/proventos (tabela `dividendos`). Persiste dados de proventos (dividendos, JCP, etc.) obtidos do StatusInvest, com upsert por chave composta `(ativo, data_com, tipo, data_pagamento)`.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `save(div: dict) -> None`
**Garante:**
1. Insere com `ON CONFLICT(ativo, data_com, tipo, data_pagamento) DO UPDATE`.
2. Colunas: `ativo`, `tipo`, `data_com`, `data_ex`, `data_pagamento`, `data_aprovacao`, `valor`, `tipo_acao`, `preco_fechamento`, `fonte`.
3. No update, atualiza: `data_ex`, `data_aprovacao`, `valor`, `tipo_acao`, `preco_fechamento`, `fonte`, `atualizado_em=CURRENT_TIMESTAMP`.
4. Não retorna a entidade (usa `dict`, não entidade de domínio).

### `save_batch(dividendos: list[dict]) -> int`
**Garante:**
1. `executemany` com mesmo INSERT...ON CONFLICT.
2. Retorna `len(dividendos)`.

### `get_all() -> list[dict]`
**Garante:**
1. `SELECT * ORDER BY data_com DESC, ativo`.

### `get_ex_hoje() -> list[dict]`
**Garante:**
1. `WHERE data_ex = date('today')`.

### `get_proximos(dias=30, dias_antes=0) -> list[dict]`
**Garante:**
1. `WHERE data_com >= (hoje - dias_antes) AND data_com <= (hoje + dias)`.

### `get_by_ativo(ativo: str) -> list[dict]`
**Garante:**
1. `WHERE ativo = ? ORDER BY data_com DESC`.

### `get_ex_range(data_inicio: str, data_fim: str) -> list[dict]`
**Garante:**
1. `WHERE data_ex BETWEEN ? AND ? ORDER BY data_ex, ativo`.

### `delete_all() -> int`
**Garante:**
1. `DELETE FROM dividendos`. Retorna rowcount.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 122 (linhas 608-729 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`DividendoRepository`) |

## Notas

- 2026-08-06 — mesma data.
- Usa `dict` como entidade (não tem classe de domínio `Dividendo`). As colunas são definidas na constante `COLUNAS_DIVIDENDOS` no topo da classe.
- O upsert por `(ativo, data_com, tipo, data_pagamento)` permite reimportar sem duplicar — atualiza campos que podem ter mudado (ex: valor ajustado).
- `tipo_acao` e `preco_fechamento` existem no schema mas raramente são populados pelo provider atual (StatusInvest não fornece esses campos na tabela de proventos simples).
