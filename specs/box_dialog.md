# BoxDialog

## Propósito

Diálogo de monitoramento de Box Spread 4 Pontas. Exibe tabela de boxes (short/long) com 26 colunas detalhadas de cada perna (CALL K1, PUT K1, CALL K2, PUT K2). Filtros por CDI mínimo, sentido (VENDIDO/COMPRADO), MOD (Americana/Europeia), e checkbox "Só viáveis". Inclui link para calculadora de Box no site opcoes.net.br.

## Contrato (Requisitos)

### `_setup_ui()`
**Garante:**
1. Filtros superiores: CDI mínimo (QDoubleSpinBox, default 0), sentido (radio VENDIDO/COMPRADO/TODOS), MOD (radio A/E/TODOS), checkbox "Só viáveis".
2. Tabela com `BoxTableModel` + `BoxSortProxy`, ordenação default por lucro_pct descendente.
3. Colunas de quantidade por perna (Q C1, Q P1, Q C2, Q P2) com formatação vermelha se ≤ 0.
4. Botão sino, exportação CSV, link externo "🔗 Calculadora Box" (abre navegador).
5. Status label com contagem + filtro ativo.

### `BoxTableModel`
**Garante:**
1. 26 colunas detalhando as 4 pernas individualmente: código, bid/ask, quantidade.
2. Foreground: verde para lucro/CDI positivo, vermelho para negativo, cinza para não viável.
3. Background: cinza escuro (`ROW_NOT_VIABLE`) para não viáveis.
4. DecorationRole: bandeira EU/US para coluna `tipo_opcao` (MOD da CALL K1).

### `BoxSortProxy`
**Garante:**
1. `set_filtro_cdi_min(valor)`: filtra por pct_cdi ≥ valor.
2. `set_filtro_sentido("VENDIDO"|"COMPRADO")`: filtra por sentido da operação.
3. `set_filtro_mod("A"|"E")`: filtra por MOD da CALL K1.
4. `set_only_viaveis(bool)`: filtra apenas viáveis.
5. Todos os filtros são combinados (AND lógico).

### `_abrir_calculadora_box()`
**Garante:**
1. Abre URL externa no navegador padrão via `QDesktopServices.openUrl()`.
2. URL hardcoded: `https://opcoes.net.br/calculadora-box/`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `collections` | `Counter` | (importado, uso não localizado) |
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, ..., QCheckBox` | UI framework |
| `PySide6.QtCore` | `Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal, QUrl` | Modelo e sinais |
| `PySide6.QtGui` | `QFont, QColor, QBrush, QDesktopServices` | Renderização + link externo |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência |
| `src.ui.desktop.flag_icons` | `flag_icon` | Ícones de bandeira |
| `src.ui.desktop.theme` | `Palette` | Paleta de cores |

## Métricas

| Linhas | 798 |
| Classes | 3 (`BoxTableModel`, `BoxSortProxy`, `BoxDialog`) |
| Testes | Não |

## Notas

- **URL hardcoded:** `https://opcoes.net.br/calculadora-box/` — não parametrizável. Se o site mudar a URL, requer alteração de código.
- **Sem filtro por ativo:** Diferente de Colar e Colar Calendário, o BoxDialog não tem seletor de ativos — mostra todos os boxes encontrados de todos os ativos.
- **`Counter` importado mas não usado** — [motivo não documentado, confirmar com o autor].
- **Box 4P requer 4 pernas simultâneas:** O modelo exibe bid/ask/quantidade de cada perna individualmente — útil para diagnosticar qual perna está sem liquidez.
- **Coluna "Sentido":** "VENDIDO" = short box (recebe hoje, paga no vencimento — cenário padrão de arbitragem). "COMPRADO" = long box (paga hoje, recebe no vencimento — cenário de taxa).
