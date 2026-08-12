# CalendarioResultadosRepository

Repositório para calendário de resultados (tabela `calendario_resultados`). Persiste eventos de publicação de resultados (ITR/DFP) obtidos da CVM (publicados) e webwallet (previstos). Upsert por `(ativo, data_publicacao, trimestre_referencia, tipo_evento)`.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `save_batch(items: list[dict]) -> int`
**Garante:**
1. `executemany` com `ON CONFLICT(ativo, data_publicacao, trimestre_referencia, tipo_evento) DO UPDATE`.
2. Colunas: `ativo`, `cnpj`, `nome_empresa`, `data_publicacao`, `trimestre_referencia`, `tipo_documento`, `tipo_evento`, `fonte`.
3. No update, atualiza: `cnpj`, `nome_empresa`, `tipo_documento`, `fonte`, `atualizado_em=CURRENT_TIMESTAMP`.

### `get_all() -> list[dict]`
**Garante:**
1. `SELECT * ORDER BY data_publicacao, ativo`.

### `get_proximos(dias=60, dias_antes=0) -> list[dict]`
**Garante:**
1. `WHERE data_publicacao >= (hoje - dias_antes) AND data_publicacao <= (hoje + dias)`.

### `get_by_ativo(ativo: str) -> list[dict]`
**Garante:**
1. `WHERE ativo = ? ORDER BY data_publicacao DESC`.

### `get_publicados(ativo="") -> list[dict]`
**Garante:**
1. `WHERE tipo_evento = 'publicado'`. Se `ativo` fornecido, filtra por ativo.
2. Ordenado por `data_publicacao DESC`.

### `get_previstos(dias=60) -> list[dict]`
**Garante:**
1. `WHERE tipo_evento = 'previsto' AND data_publicacao >= hoje AND data_publicacao <= (hoje + dias)`.

### `delete_all() -> int`
**Garante:**
1. `DELETE FROM calendario_resultados`.

### `delete_by_fonte(fonte: str) -> int`
**Garante:**
1. `DELETE WHERE fonte = ?`. Permite limpar só CVM ou só webwallet.

### `replace_by_fonte(fonte: str, items: list[dict]) -> int`
**Garante:**
1. DELETE + INSERT na **mesma transação** com rollback em caso de falha.
2. DELETE `WHERE fonte = ?`.
3. Se `items` não vazio, `executemany` com `ON CONFLICT(ativo, data_publicacao, trimestre_referencia, tipo_evento) DO UPDATE`.
4. Substitui atomicamente o par `delete_by_fonte` + `save_batch`.

### `get_cnpj_ticker_map() -> dict[str, str]`
**Garante:**
1. `SELECT DISTINCT cnpj, ativo WHERE cnpj IS NOT NULL AND cnpj != ''`.
2. Retorna dict `{cnpj: ativo}` para mapeamento usado pelo provider CVM.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 126 (linhas 869-994 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`CalendarioResultadosRepository`) |

## Notas

- 2026-08-06 — mesma data.
- A chave de conflito `(ativo, data_publicacao, trimestre_referencia, tipo_evento)` permite que um mesmo ativo tenha eventos "previsto" e "publicado" para a mesma data sem conflito.
- `get_cnpj_ticker_map` é usado pelo `CalendarioResultadosCVMProvider.set_cnpj_ticker_map()` para que o provider CVM saiba traduzir CNPJ → ticker.
- Colunas definidas na constante `COLUNAS_CALENDARIO_RESULTADOS`.
