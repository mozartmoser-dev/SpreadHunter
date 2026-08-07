# ColarDialog

## Propósito

Diálogo de monitoramento de Colares Protetivos (Collar Tradicional). Exibe tabela com 22 colunas de resultados de colar, filtros por ativo (texto ou checklist), filtros por Pop↑/Pop↓ mínimos, Top-N por ativo, e variante (Base/Otimizada/Todas). Suporta modo scanner automático com sinais `iniciar_scan_signal`/`parar_scan_signal` comunicando-se com o `MonitorWorker`. Inclui visualização detalhada de montagem com payoff, gráfico histórico, explicação da estratégia e exportação CSV.

## Contrato (Requisitos)

### `_setup_ui()`
**Garante:**
1. Painel esquerdo (200px fixo): filtro de ativo com debounce 200ms, filtros Pop min, Top-N spinner (0-20), combo de variante, lista de ativos com checkboxes, botão (Des)marcar TODOS.
2. Tabela principal com `ColarTableModel` + `ColarSortProxy`, ordenação default pela coluna 3 (Score descendente).
3. Botão "🔍 Iniciar Scanner" que alterna para "⏹ Parar Scanner" — controla `_auto_mode`.
4. Botão sino (🔔) com toggle visual para alerta sonoro.
5. Botão "📥 Export CSV" usando `exportar_monitor_csv`.
6. Status label mostrando contagem + estado RTD.

### Filtros (`ColarSortProxy`)
**Garante:**
1. `set_filtro_ativo(texto)`: filtro por substring case-insensitive no ativo.
2. `set_filtro_lista(ativos: set)`: filtro por conjunto exato de ativos (checklist).
3. `set_filtro_pop_upside(minimo)` / `set_filtro_pop_downside(minimo)`: filtro por probabilidade mínima.
4. `set_top_n(n)`: mantém só as N melhores linhas por ativo (coluna de ordenação atual).
5. `set_filtro_variante("Base"|"Otimizada"|"Todas")`: filtra por `UserRole+1` (is_otimizado).
6. `_recompute_top_n()`: reagrupa por ativo, ordena cada grupo, mantém top N.

### `_mostrar_detalhes(r: ResultadoColar)`
**Garante:**
1. Diálogo modal com form layout mostrando: vencimento, dias, compra ativo (preço × qtd), compra PUT, venda CALL, custo líquido, pior retorno, custos B3, IR, pior líquido, %CDI.
2. Botões de ação: 📊 Payoff, 📈 Ver Variação, 📊 Ver Gráfico, 🔍 Explicar, 📋 Basket PNT, 📋 Exportar Debug.
3. Para variantes otimizadas: exibe estágio (Rendimento/Proteção/Platô), ratios call/put, quantidade de ações.

### `restaurar_selecao(ativos: list[str])`
**Garante:**
1. Marca checkboxes da lista de ativos conforme a lista fornecida.
2. Aplica filtro de lista imediatamente.

### Whitelist
**Garante:**
1. `ler_whitelist_colar(db_path)` lê `white_list_colar` do `ParametroRepository`.
2. Formato: string CSV (ex: "PETR4,VALE3,ITUB4").

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, ..., QComboBox` | UI framework |
| `PySide6.QtCore` | `Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, QStringListModel, Signal` | Modelo e sinais |
| `PySide6.QtGui` | `QFont, QColor, QBrush` | Renderização |
| `src.infrastructure.integrations.opcoesnet_client` | `OpcoesNetClient` | Histórico de preços |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência de colunas |
| `src.ui.desktop.copy_utils` | `copiar_texto_formatado, copiar_figura_clipboard, salvar_figura_arquivo` | Exportação |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.ui.desktop.constants` | `SELETOR_TODOS` | Constante de UI |
| `src.domain.services.calendario_b3` | `dc_to_du` | Dias corridos → úteis |

## Métricas

| Linhas | 2114 |
| Classes | 3 (`ColarTableModel`, `ColarSortProxy`, `ColarDialog`) |
| Testes | Não (testado indiretamente via integração) |

## Notas

- **`ColarTableModel._items` são dicts, não objetos tipados** — diferente dos modelos de tabela principais que usam DTOs. Isso é porque os resultados de colar são serializados para dict antes de chegar à UI.
- **Debounce de filtro:** 200ms via `QTimer.singleShot`. O timer é resetado a cada `textChanged`.
- **`_carregar_todos_ativos()`:** Método referenciado mas não visível no início do arquivo — provavelmente definido mais abaixo. Popula a lista de ativos a partir dos instrumentos disponíveis.
- **Sinais `iniciar_scan_signal` / `parar_scan_signal`:** Emitidos para o `MainWindow` que repassa ao `MonitorWorker` para controlar varredura automática de colares.
- **`_restart_scan_if_auto()`:** Se o scanner está em modo auto e o usuário muda a seleção de ativos, reinicia o scan automaticamente.
