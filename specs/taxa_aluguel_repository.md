# TaxaAluguelRepository

Repositório para taxas de aluguel de ações (tabela `taxas_aluguel`). Persiste dados de aluguel obtidos do InvestSite com upsert por `(ativo, data)`. Suporta consulta da taxa mais recente por ativo.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `save(taxa: TaxaAluguel) -> TaxaAluguel`
**Garante:**
1. Insere com `ON CONFLICT(ativo, data) DO UPDATE`.
2. Colunas: `ativo`, `data`, `taxa_atual`, `taxa_7d`, `taxa_28d`.
3. No update, atualiza `taxa_atual`, `taxa_7d`, `taxa_28d`, `created_at=CURRENT_TIMESTAMP`.
4. Atribui `taxa.id = cursor.lastrowid`.

### `get_latest_by_ativo(ativo: str) -> TaxaAluguel | None`
**Garante:**
1. `SELECT * WHERE ativo = ? ORDER BY data DESC LIMIT 1`.
2. Retorna `None` se não encontrado.

### `get_latest_all() -> dict[str, TaxaAluguel]`
**Garante:**
1. Subquery: `MAX(data) GROUP BY ativo` + JOIN para pegar a linha completa.
2. Retorna dict `{ativo: TaxaAluguel}`.

### `_row_to_entity(row) -> TaxaAluguel`
**Garante:**
1. Constrói `TaxaAluguel` a partir de `sqlite3.Row`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.domain.entities.taxa_aluguel` | `TaxaAluguel` | Entidade |
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 59 (linhas 808-866 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`TaxaAluguelRepository`) |

## Notas

- 2026-08-06 — mesma data.
- `get_latest_all` usa subquery com `GROUP BY` + `MAX(data)`, que é idiomático para SQLite mas pode ser lento com muitas linhas (não há índice explícito além do UNIQUE `(ativo, data)`).
- Diferente de `DividendoRepository` e `FeriadoB3Repository`, este repositório usa uma entidade de domínio (`TaxaAluguel`), não `dict`.
