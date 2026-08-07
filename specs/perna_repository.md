# PernaRepository

Repositório para `PernaOperacao` (tabela `pernas_operacao`). Cada perna pertence a uma estrutura e representa uma operação individual (compra/venda de ativo, CALL ou PUT) com quantidade, lado e ordem.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `save(perna: PernaOperacao) -> PernaOperacao`
**Garante:**
1. Insere na tabela `pernas_operacao` com colunas: `estrutura_id`, `codigo`, `lado`, `quantidade`, `profundidade`, `ordem`.
2. `lado` serializado via `.value` (enum `Lado`).
3. Atribui `perna.id = cursor.lastrowid`.

### `get_by_estrutura(estrutura_id: int) -> list[PernaOperacao]`
**Garante:**
1. `SELECT * WHERE estrutura_id = ? ORDER BY ordem`.
2. Reconstrói entidades com `Lado(row["lado"])`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.domain.entities.perna_operacao` | `PernaOperacao`, `Lado` | Entidades |
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 41 (linhas 563-603 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`PernaRepository`) |

## Notas

- 2026-08-06 — mesma data do arquivo.
- Repositório mais simples do sistema — apenas save e get_by_estrutura. Sem get_all, sem delete individual.
- `ordem` é usado para ordenar as pernas dentro de uma estrutura (ex: perna 0 = ativo, perna 1 = PUT, perna 2 = CALL).
