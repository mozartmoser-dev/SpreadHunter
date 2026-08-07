# OportunidadeRepository

Repositório para a entidade `Oportunidade` (tabela `oportunidades`). Persiste snapshots de mercado de oportunidades detectadas (SBTH, Box, etc.) com classificação e métricas de CDI.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path` para uso nas queries.

### `save(oportunidade: Oportunidade) -> Oportunidade`
**Garante:**
1. Insere na tabela `oportunidades` com colunas: `instrumento_id`, `preco_ativo`, `strike`, `dias`, `cdi_periodo`, `custo_sbth`, `pct_ganho_sbth`, `pct_cdi_sbth`, `custo_box`, `pct_ganho_box`, `pct_cdi_box`, `classificacao`, `operacao`, `snapshot_mercado`.
2. `classificacao` serializado via `.value` (enum).
3. `snapshot_mercado` serializado como JSON string.
4. Atribui `oportunidade.id = cursor.lastrowid`.
5. Retorna o objeto mutado.

### `get_all() -> list[Oportunidade]`
**Garante:**
1. `SELECT * FROM oportunidades` sem filtro.
2. Reconstrói entidades via `_row_to_entity`, incluindo `json.loads` do snapshot.

### `get_historico_completo(limite=5000) -> list[dict]`
**Garante:**
1. JOIN com `instrumentos_base` para incluir `ativo`.
2. Ordenado por `created_at DESC`.
3. Retorna lista de dicts (não entidades) com campos planos para exibição em tabela.

### `get_historico_com_estrutura(limite=5000) -> list[dict]`
**Garante:**
1. JOIN com `instrumentos_base` + LEFT JOIN `estruturas_operacionais` + LEFT JOIN `pernas_operacao`.
2. Reconstrói hierarquia: oportunidade → estruturas → pernas.
3. Deduplica estruturas e pernas dentro de cada oportunidade (uma row do SQL pode ter múltiplas pernas).
4. Ordenado por `created_at DESC, e.id, p.ordem`.

### `delete_by_id(o_id: int) -> bool`
**Garante:**
1. `PRAGMA foreign_keys=ON` para cascata.
2. Deleta na ordem: pernas → estruturas → oportunidade (evita violação de FK).
3. Retorna `True` se alguma linha foi afetada.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `json` | `json` | Serialização de snapshot |
| `src.domain.entities.oportunidade` | `Oportunidade`, `ClassificacaoOp` | Entidades |
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 179 (linhas 303-481 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`OportunidadeRepository`) |

## Notas

- 2026-08-06 — última modificação do arquivo `repositories.py` como um todo.
- `get_historico_com_estrutura` faz um JOIN pesado (4 tabelas) e reconstrói a hierarquia em Python. Para volumes altos (>5000), pode ser lento.
- `delete_by_id` usa `PRAGMA foreign_keys=ON` (diferente de `InstrumentoRepository.delete_all` que usa OFF) porque aqui queremos cascata real.
- Não há cache neste repositório — todas as queries vão direto ao banco.
