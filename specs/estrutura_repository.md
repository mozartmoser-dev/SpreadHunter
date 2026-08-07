# EstruturaRepository

Repositório para `EstruturaOperacional` (tabela `estruturas_operacionais`). Cada estrutura pertence a uma oportunidade e descreve o tipo (colar, box, etc.) com coeficientes de mercado e taxa de ganho.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `save(estrutura: EstruturaOperacional) -> EstruturaOperacional`
**Garante:**
1. Insere na tabela `estruturas_operacionais` com colunas: `oportunidade_id`, `tipo`, `coefic_alvo`, `coefic_mercado`, `taxa_ganho`.
2. `tipo` serializado via `.value` (enum `TipoEstrutura`).
3. Atribui `estrutura.id = cursor.lastrowid`.

### `get_by_id(estrutura_id: int) -> EstruturaOperacional | None`
**Garante:**
1. `SELECT * WHERE id = ?`.
2. Retorna `None` se não encontrado.

### `get_all() -> list[EstruturaOperacional]`
**Garante:**
1. `SELECT *` sem filtro.

### `get_by_oportunidade(oportunidade_id: int) -> list[EstruturaOperacional]`
**Garante:**
1. `SELECT * WHERE oportunidade_id = ?`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.domain.entities.estrutura_operacional` | `EstruturaOperacional`, `TipoEstrutura` | Entidades |
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 77 (linhas 484-560 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`EstruturaRepository`) |

## Notas

- 2026-08-06 — mesma data do arquivo `repositories.py`.
- Repositório simples, sem cache, sem métodos de deleção individuais (remoção é feita via `OportunidadeRepository.delete_by_id` com `PRAGMA foreign_keys=ON`).
