# MonitorTableModel

## Propósito

`QAbstractTableModel` para a tabela principal de oportunidades (Box, SBTH, Box+SBTH). Renderiza 25 colunas com formatação condicional de cores (verde/vermelho/amarelo/roxo), ícones de bandeira para tipo de opção (MOD), tachado para custos não aplicáveis, e tooltips detalhados por coluna. Suporta detecção de hash para evitar repinturas desnecessárias.

## Contrato (Requisitos)

### `atualizar(oportunidades: list[OportunidadeMonitor])`
**Garante:**
1. Calcula hash baseado em `(len, id(primeiro), id(último))` para evitar rebuild se os dados não mudaram.
2. Se hash igual ao anterior (`_ultimo_hash`), retorna sem alterar o modelo.
3. Usa `layoutAboutToBeChanged`/`layoutChanged` (não `beginResetModel`/`endResetModel`).
4. Reconstrói `_key_map` mapeando `instrumento_id` → índice.

### `data(index, role)`
**Garante:**
1. **DisplayRole:** Formata valores monetários (R$ X.XX), percentuais, datas (DD/MM/YYYY), indicadores de liquidez (✓/✗/✓~).
2. **BackgroundRole:** Cores de fundo por classificação: azul (1BOX), ciano (2SBTH), roxo (3BOXSBTH), cinza escuro (não viável), laranja (leilão).
3. **ForegroundRole:** Verde para ganhos/liquidez positivos, vermelho para negativos, amarelo para CDI, tachado para custos não aplicáveis.
4. **FontRole:** Negrito para colunas principais (label_tipo, ganho_bruto, ganho_liq, rent_cdi_bruto, rent_cdi_liq, liq_indicator); tachado para custos não aplicáveis.
5. **DecorationRole:** Bandeira EU/US para coluna `tipo_opcao`.
6. **TextAlignmentRole:** Centralizado para colunas numéricas, esquerda para texto.

### `headerData(section, orientation, role)`
**Garante:**
1. Tooltips detalhados para todas as 25 colunas com disclosure de custos B3.
2. Nomes de coluna com sufixo "(i)" indicando colunas interativas (ordenáveis/filtráveis).

### `get_oportunidade(row) -> OportunidadeMonitor | None`
**Garante:**
1. Retorna `OportunidadeMonitor` no índice ou `None` se fora do range.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtCore` | `Qt, QAbstractTableModel, QModelIndex` | Modelo Qt |
| `PySide6.QtGui` | `QColor, QBrush, QFont, QIcon` | Renderização |
| `src.application.dtos.dtos` | `OportunidadeMonitor` | DTO de entrada |
| `src.ui.desktop.flag_icons` | `flag_icon` | Ícones de bandeira |
| `src.ui.desktop.theme` | `Palette` | Paleta de cores |

## Métricas

| Linhas | 319 |
| Classes | 1 |
| Testes | Não (testado indiretamente via `test_fase3.py` que verifica integração UI) |

## Notas

- **Uso de `layoutAboutToBeChanged` em vez de `beginResetModel`:** Preserva seleção e scroll position durante atualizações. Vendidas e Venda Coberta usam `beginResetModel` — inconsistência entre modelos [motivo não documentado, confirmar com o autor].
- **Hash de otimização:** Só recalcula se `(len, id[0], id[-1])` mudar. Isso pode causar falsos positivos (não repintar quando deveria) se o conteúdo das oportunidades mudar mas o tamanho da lista e as referências das pontas forem as mesmas. POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão.
- **CUSTOS_DISCLOSURE:** Constante de módulo reusada nos tooltips para explicar que custos incluem B3 + IR.
- **Colunas escondidas por default:** 13 das 25 colunas são ocultas inicialmente (custo_box, custo_sbth, liq_put, liq_call, money, of_compra_put, of_venda_call, qul_put, qul_call, tipo_opcao, cod_put, cod_call, leilao_display, label_detectado).
