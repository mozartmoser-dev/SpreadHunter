# PutRatioDialog

## Propósito

Diálogo de monitoramento de Put Ratio Spread. Exibe tabela com 26 colunas detalhando o par PUT K1 (comprada) × PUT K2 (vendida). Inclui delegate customizado `_PerfilDelegate` que renderiza barra horizontal colorida com probabilidades de perda/tenda/crédito. Filtros por ativo (checklist), CDI mínimo, proteção mínima, Top-N. Cálculo de perfil de payoff via `scipy.stats.norm` (Black-Scholes). Suporta modo scanner automático com sinais.

## Contrato (Requisitos)

### `_setup_ui()`
**Garante:**
1. Painel esquerdo com: filtro de ativo (texto + checklist), CDI mínimo (QDoubleSpinBox), proteção mínima %, Top-N spinner, combo de variante.
2. Tabela com `PutRatioTableModel` + `PutRatioSortProxy`.
3. Delegate `_PerfilDelegate` aplicado à coluna "Perfil" — renderiza barra tri-colorida (perda/slope/crédito).
4. Botão sino, exportação CSV, status label.

### `_perfil_payoff(r) -> tuple`
**Garante:**
1. Calcula probabilidades via `scipy.stats.norm.cdf`: p_perda (S < BE), p_slope (BE < S < K1), p_credito (S > K1).
2. Usa IV da PUT e dias até vencimento (T = dias/365).

### `_PerfilDelegate`
**Garante:**
1. `paint()`: desenha barra horizontal com 3 segmentos coloridos — vermelho (perda), verde (slope), azul (crédito).
2. Exibe percentuais como texto dentro de cada segmento (se largura > 14px).
3. `sizeHint()`: altura fixa de 34px.
4. Usa `UserRole` nos dados para receber a tupla `(p_loss, p_slope, p_credit)`.

### `PutRatioTableModel`
**Garante:**
1. 26 colunas: Ativo, Spot, Ratio, K1, K2, Ask K1, Bid K2, Crédito, Yield%, %CDI, Prot%, BE, POP%, Perfil, IV Rank, IV Pct, Score, Zona, Dias, Venc, Cód.Put, Q K1, Q K2, Detectado.
2. `UserRole` na coluna "Perfil" retorna tupla de probabilidades para o delegate.

### `PutRatioSortProxy`
**Garante:**
1. `set_filtro_cdi_min(valor)`: filtra por yield_cdi.
2. `set_filtro_protecao_min(valor)`: filtra por protecao_pct.
3. `set_filtro_lista(ativos)`: filtro por conjunto de ativos.
4. `set_top_n(n)`: Top-N por ativo.

### Whitelist
**Garante:**
1. `ler_whitelist_put_ratio(db_path)` lê `white_list_put_ratio` do banco.
2. Formato CSV idêntico ao colar.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `math` | stdlib | Cálculo de sigma |
| `scipy.stats` | `norm` | `cdf` para probabilidades Black-Scholes |
| `PySide6.QtCore` | `Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal, QUrl, QRect` | Modelo e sinais |
| `PySide6.QtGui` | `QFont, QColor, QBrush, QDesktopServices, QPainter, QPen` | Renderização |
| `PySide6.QtWidgets` | `QDialog, QStyle, QVBoxLayout, ..., QSpinBox` | UI framework |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência |
| `src.ui.desktop.constants` | `SELETOR_TODOS` | Constante |
| `src.ui.desktop.theme` | `Palette` | Cores |

## Métricas

| Linhas | 865 |
| Classes | 4 (`_PerfilDelegate`, `PutRatioTableModel`, `PutRatioSortProxy`, `PutRatioDialog`) |
| Testes | Não |

## Notas

- **Dependência pesada de scipy:** `from scipy.stats import norm` no topo do arquivo — import caro que pode atrasar a abertura do diálogo. Se o diálogo for aberto antes do scipy estar carregado, pode causar delay perceptível.
- **`_PerfilDelegate.sizeHint` usa `__import__` inline:** `__import__('PySide6.QtCore').QSize(200, 34)` — hack para evitar import circular ou dependência de módulo. POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: `__import__` é frágil e desnecessário (PySide6.QtCore já está importado no topo).
- **Colunas PUT-only:** Diferente dos outros diálogos, só existem colunas de PUT (K1 comprada, K2 vendida) — sem CALL.
- **Cálculo de perfil via Black-Scholes:** O `_perfil_payoff` usa `norm.cdf` com `d = (S - K) / (S × σ × √T)` — aproximação lognormal. A fórmula assume que o ativo segue movimento browniano geométrico.
