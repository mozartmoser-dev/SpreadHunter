# column_utils

Utilitários para persistência de ordem e largura de colunas em `QTableView`/`QHeaderView` via `QSettings`. Implementa checksum de colunas para detectar mudanças no schema da tabela e invalidar configurações salvas que não correspondem mais à estrutura atual.

Usado por `main_window.py`, `mpp_dialog.py` e diversos diálogos de monitoramento.

## Contrato (Requisitos)

### `salvar_ordem_colunas(header, key, colunas=None) -> None`
**Garante:**
1. Persiste a ordem lógica das colunas (`header.logicalIndex`) em `QSettings("Spreadhunter", "DesktopMonitor")`.
2. Se `colunas` fornecida, salva checksum SHA256 (12 chars) para detectar mudanças de schema.
3. Silencia exceções.

### `restaurar_ordem_colunas(header, key, colunas=None) -> None`
**Garante:**
1. Se checksum salvo difere do atual (via `_ordem_invalida`), remove as chaves QSettings e retorna sem restaurar.
2. Lê ordem salva, valida bounds, aplica `header.moveSection`.
3. Silencia exceções.

### `salvar_largura_colunas(header, key) -> None`
**Garante:**
1. Salva array de larguras (`header.sectionSize`) em QSettings.
2. Silencia exceções.

### `restaurar_largura_colunas(header, key) -> None`
**Garante:**
1. Lê array de larguras salvo e aplica `header.resizeSection` para cada coluna dentro dos bounds.
2. Silencia exceções.

### `detectar_incompatibilidade(workspace_snapshot) -> dict[str, tuple[int, int]]`
**Garante:**
1. Para 7 chaves conhecidas (`main_table_order`, `vendidas_table_order`, `coberta_table_order`, `colar_table_order`, `colar_cal_table_order`, `box_table_order`, `mpp_table_order`), compara número de colunas no snapshot vs QSettings atual.
2. Retorna dict `{chave: (n_snapshot, n_atual)}` apenas para chaves com diferença.

### `limpar_colunas_incompativeis(header, order_key, width_key) -> bool`
**Garante:**
1. Remove chaves QSettings de ordem/largura se o número de colunas salvo difere do `header.count()` atual.
2. Retorna `True` se removeu alguma chave.

### `limpar_e_restaurar_colunas(header, order_key, width_key, colunas=None) -> None`
**Garante:**
1. Atalho que chama `limpar_colunas_incompativeis` + `restaurar_ordem_colunas` + `restaurar_largura_colunas`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtCore` | `QSettings` | Persistência de ordem/largura |
| `hashlib` | — | SHA256 para checksum de colunas |

## Métricas

| Linhas | 153 |
| Testes | Sim (2 arquivos: `test_column_crash.py`, `test_vendidas_column_persist.py`) |

## Notas

- **Data da última modificação:** 2026-07-24
- O checksum usa `hashlib.sha256` truncado para 12 caracteres hex. Colisões são possíveis mas improváveis dado o espaço de 2^48.
- A função `_ordem_invalida` retorna `True` se `colunas is None` ou checksum ausente — isso significa que chamar `restaurar_ordem_colunas` sem passar `colunas` nunca invalida a ordem salva.
- `_CHAVES_ORDEM_COLUNAS` tem 7 entradas mas há diálogos que usam chaves próprias (ex: `estudos_calendario_order` no `estudos_calendario_dialog.py`). Essas chaves não são cobertas por `detectar_incompatibilidade`.
- Relacionado a AGENTS.md: "Segfault ao arrastar coluna" — os handlers `sectionMoved` usam `QTimer.singleShot(0, ...)` para evitar conflito com `layoutChanged` do sort.
