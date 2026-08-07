# VendidasTableModel

## Propósito

`QAbstractTableModel` para a tabela de oportunidades vendidas (Box Vendido, SBTH Vendida). Estrutura similar ao `MonitorTableModel` mas com DTO `OportunidadeVendida` e sem coluna `leilao_display` visível no foreground condicional de viabilidade. Usa `beginResetModel`/`endResetModel` (diferente do modelo principal que usa `layoutAboutToBeChanged`).

## Contrato (Requisitos)

### `atualizar(items: list[OportunidadeVendida])`
**Garante:**
1. Hash de otimização idêntico ao `MonitorTableModel` — `(len, id[0], id[-1])`.
2. Usa `beginResetModel()`/`endResetModel()` (reset completo, perde seleção/scroll).
3. Substitui a lista interna `_items` completamente.

### `data(index, role)`
**Garante:**
1. **DisplayRole:** Mesma formatação do `MonitorTableModel` (R$ X.XX, datas DD/MM/YYYY, indicadores de liquidez).
2. **BackgroundRole:** Azul para BOX, ciano para SBTH, cinza para não viável, laranja para leilão.
3. **ForegroundRole:** Verde/vermelho para ganhos e liquidez. "BOX" no label_tipo usa azul, "SBTH" usa ciano.
4. **FontRole:** Negrito para colunas principais; tachado para custos não aplicáveis (custo_box em SBTH, custo_sbth em BOX).
5. **DecorationRole:** Bandeira EU/US para `tipo_opcao`.

### Colunas escondidas por default
**Garante:**
1. 11 colunas ocultas: custo_box, custo_sbth, liq_put, liq_call, money, of_compra_put, of_venda_call, qul_put, qul_call, cod_put, cod_call, tipo_opcao, label_detectado.
2. Diferente do modelo principal: `leilao_display` NÃO é escondido por default neste modelo.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtCore` | `Qt, QAbstractTableModel` | Modelo Qt |
| `PySide6.QtGui` | `QColor, QBrush, QFont, QIcon` | Renderização |
| `src.application.dtos.dtos_vendida` | `OportunidadeVendida` | DTO de entrada |
| `src.ui.desktop.flag_icons` | `flag_icon` | Ícones de bandeira |
| `src.ui.desktop.theme` | `Palette` | Paleta de cores |

## Métricas

| Linhas | 264 |
| Classes | 1 |
| Testes | Não (testado indiretamente via testes de integração) |

## Notas

- **`beginResetModel` vs `layoutAboutToBeChanged`:** Este modelo usa reset completo, diferente do `MonitorTableModel`. Motivo não documentado. POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: reset completo causa flicker e perde a posição de scroll a cada atualização (a cada ~3s no ciclo do worker).
- **Lógica de background simplificada:** Diferente do modelo principal, classificação é binária (BOX vs SBTH) — não existe "3BOXSBTH" nas vendidas.
- **`_FG_STRIKEOUT`** mapeado para `Palette.TEXT_MUTED` (não para uma cor de tachado dedicada como no modelo principal que usa `Palette.STRIKEOUT_COLOR`).
