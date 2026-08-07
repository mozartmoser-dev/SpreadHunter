# VendaCobertaTableModel

## Propósito

`QAbstractTableModel` para a tabela de venda coberta (Taxa). Renderiza oportunidades de venda coberta (vendida + comprada) com DTO `OportunidadeVendaCoberta`. Background azul escuro para operações compradas, azul claro para vendidas. Simplificado em relação aos outros modelos — sem colunas PUT (usa "-" para campos de PUT).

## Contrato (Requisitos)

### `atualizar(items: list[OportunidadeVendaCoberta])`
**Garante:**
1. Hash de otimização: `(len, id[0], id[-1])`.
2. Usa `beginResetModel()`/`endResetModel()`.
3. Ordenação externa (feita na `MainWindow` antes de emitir): `coberta.sort(key=lambda o: (not o.viavel, -o.pct_cdi))`.

### `data(index, role)`
**Garante:**
1. **DisplayRole:** Campos de PUT (`liq_put_display`, `of_compra_put`, `qul_put`) sempre retornam "-" (venda coberta não usa PUT).
2. **BackgroundRole:** Laranja para leilão, cinza escuro para não viável, azul escuro (`#0d1a2d`) para TAXA_COMPRADA, azul (`ROW_BOX`) para viável.
3. **ForegroundRole:** Verde para ganhos/liquidez positivos, vermelho para negativos, amarelo para CDI, ciano para label_tipo.
4. **FontRole:** Apenas negrito para colunas principais (sem tachado — não há custos não aplicáveis visíveis).
5. **DecorationRole:** Bandeira EU/US para `tipo_opcao`.

### Colunas escondidas por default
**Garante:**
1. 11 colunas ocultas (mesmo conjunto das vendidas): custo_box, custo_sbth, liq_put, liq_call, money, of_compra_put, of_venda_call, qul_put, qul_call, cod_put, cod_call, tipo_opcao, label_detectado.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtCore` | `Qt, QAbstractTableModel` | Modelo Qt |
| `PySide6.QtGui` | `QColor, QBrush, QFont, QIcon` | Renderização |
| `src.application.dtos.dtos_venda_coberta` | `OportunidadeVendaCoberta` | DTO de entrada |
| `src.ui.desktop.flag_icons` | `flag_icon` | Ícones de bandeira |
| `src.ui.desktop.theme` | `Palette` | Paleta de cores |

## Métricas

| Linhas | 215 |
| Classes | 1 |
| Testes | Não (testado indiretamente via integração) |

## Notas

- **Estrutura de colunas idêntica aos outros modelos de tabela** (25 colunas com mesmas chaves), mas ~13 colunas são irrelevantes para venda coberta (todas as de PUT + custos de box/sbth). Isso causa desperdício de memória e complexidade desnecessária. POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: refatorar para modelo com menos colunas ou herança.
- **`_BG_COMPRADA`** hardcoded como `#0d1a2d` (não usa Palette). Inconsistente com o resto do tema.
- **`_data()` method inline:** Diferente de `MonitorTableModel` e `VendidasTableModel` que têm `_display()`, `_background()`, `_foreground()` como métodos separados, este modelo implementa tudo no `data()` principal. Inconsistência de estilo.
