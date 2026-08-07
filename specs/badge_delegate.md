# BadgeDelegate

Delegate de pintura customizada para `QTableView` que renderiza badges (pílulas com cantos arredondados) nas colunas `label_tipo` e `liq_indicator`. Substitui o texto simples por badges coloridos que indicam o tipo de operação (BOX, SBTH, BOX+SBTH) e o indicador de liquidez (✓, ✗, ✓~).

## Contrato (Requisitos)

### `BadgeDelegate(parent=None) -> None`
**Garante:**
1. Herda de `QStyledItemDelegate`.

### `paint(painter, option, index) -> None`
**Garante:**
1. Se a coluna NÃO for `label_tipo` ou `liq_indicator`, delega para `super().paint()`.
2. Se o model for `QSortFilterProxyModel`, usa `sourceModel()` para acessar `COLUMNS`.
3. Desenha fundo da célula (BackgroundRole ou alternância padrão #1e1e34/#1a1a2e).
4. Desenha highlight de seleção (#2d4a7a) ou hover (#24243e).
5. Renderiza badge com cor de fundo e texto baseados no conteúdo:

| Coluna | Conteúdo | Cor de fundo | Cor de texto |
|---|---|---|---|
| `label_tipo` | BOX+SBTH | Roxo (#9b59b6, 35α) | #be8ee1 |
| `label_tipo` | BOX | Azul (#2d4a7a, 50α) | #7fb7ff |
| `label_tipo` | SBTH | Ciano (#1abc9c, 35α) | #1abc9c |
| `liq_indicator` | ✓ | Verde (#2ecc71, 35α) | #2ecc71 |
| `liq_indicator` | ✗ | Vermelho (#e74c3c, 35α) | #e74c3c |
| `liq_indicator` | outro | Laranja (#f39c12, 35α) | #f39c12 |

6. Largura máxima do badge: 90px para `label_tipo`, 50px para `liq_indicator`.
7. Badge centralizado horizontal e verticalmente na célula.
8. Texto em negrito, tamanho 8pt (`label_tipo`) ou 10pt (`liq_indicator`).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QStyledItemDelegate`, `QStyle` | Base do delegate + enum State (import lazy) |
| `PySide6.QtGui` | `QPainter`, `QColor`, `QPen`, `QBrush` | Renderização do badge |
| `PySide6.QtCore` | `Qt`, `QRectF`, `QSortFilterProxyModel` | Constantes + proxy model (import lazy) |

## Métricas

| Linhas | 100 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-07-13
- O delegate lida com `QSortFilterProxyModel` desempacotando para `sourceModel()` e acessando `COLUMNS` — assume que todo modelo fonte tem o atributo `COLUMNS`.
- Para `liq_indicator` com valor diferente de ✓/✗, o badge mostra "✓~" em laranja. Isso parece ser um estado intermediário de liquidez "parcial".
- `QStyle` é importado lazy dentro de `paint()` — poderia ser importado no topo.
- O delegate não trata o caso de `model.COLUMNS` não existir no modelo fonte. Se o proxy model for usado com um modelo sem `COLUMNS`, ocorrerá `AttributeError`. **POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão.**
