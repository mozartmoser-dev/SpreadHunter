# HistoricoDialog

## Propósito

Diálogo de histórico de operações — visualiza operações registradas no banco com gráfico de candlestick interativo (Matplotlib + opcoes.net.br). Inclui hover tooltip com O/H/L/C/Volume, linhas de strike PUT/CALL, bandas de ±3σ, e inset com distribuição gaussiana. Abas: Gráfico, Operações (lista de registros), Análise (estatísticas). Suporta exportação de figura para clipboard.

## Contrato (Requisitos)

### `plot_historico(parent, ativo, preco_atual, strike_put, strike_call, n_sessoes)`
**Garante:**
1. Obtém candles históricos via `OpcoesNetClient.get_stock_history_formatted(ativo)`.
2. Renderiza gráfico de candlestick (Matplotlib FigureCanvas):
   - Barras OHLC com verde (fechou acima da abertura) e vermelho (fechou abaixo).
   - Linhas tracejadas para strikes PUT/CALL com labels coloridos.
   - Preenchimento entre strikes (alpha 0.04, azul claro).
   - Bandas de ±1σ a ±3σ (linhas pontilhadas amarelas).
   - Inset com distribuição gaussiana e marcadores de strike.
   - Hover annotation: ao passar o mouse, mostra tooltip com data, O/H/L/C, volume.
3. Segundo subplot (se dados de volatilidade disponíveis): volume normalizado + vol histórica (azul) e implícita.
4. Ajusta ylim para incluir bandas de sigma.

### Aba "Operações"
**Garante:**
1. Tabela com operações registradas: data, ativo, tipo, strike, custo, resultado, %CDI, vencimento.
2. Ordenável por coluna.
3. Duplo clique abre detalhes da operação.

### Aba "Análise"
**Garante:**
1. Estatísticas agregadas: total de operações, % vencedoras, resultado acumulado, resultado médio, maior ganho, maior perda.
2. Gráfico de evolução do patrimônio (linha acumulada).
3. Gráfico de distribuição de resultados (histograma).

### `_setup_ui()`
**Garante:**
1. QTabWidget com 3 abas.
2. Botões: Exportar CSV, Atualizar, Fechar.
3. Filtro por ativo (combobox com ativos que têm operações registradas).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `json` | stdlib | (importado, uso não localizado no trecho lido) |
| `datetime` | `datetime` | Datas |
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, ..., QGroupBox` | UI framework |
| `PySide6.QtCore` | `Qt, QAbstractTableModel` | Modelo |
| `PySide6.QtGui` | `QFont, QColor, QBrush` | Renderização |
| `src.ui.desktop.copy_utils` | `copiar_texto_formatado, copiar_figura_clipboard, salvar_figura_arquivo` | Exportação |
| `src.ui.desktop.theme` | `Palette` | Cores |

### Dependências dinâmicas (dentro de `plot_historico`)
| Módulo | Símbolo | Uso |
|---|---|---|
| `numpy` | `np` | Arrays de preços |
| `matplotlib.backends.backend_qtagg` | `FigureCanvasQTAgg` | Canvas Qt |
| `matplotlib.figure` | `Figure` | Figura |
| `matplotlib.dates` | `mdates` | Formatação de datas |
| `scipy.stats` | `norm` | Distribuição gaussiana |
| `src.infrastructure.integrations.opcoesnet_client` | `OpcoesNetClient` | Candles históricos |

## Métricas

| Linhas | 583 |
| Classes | 1+ (`HistoricoDialog`, `OperacoesTableModel`) |
| Testes | Não |

## Notas

- **Dependências pesadas importadas dentro da função `plot_historico`:** `numpy`, `matplotlib`, `scipy.stats` — import lazy para evitar carregamento na inicialização da aplicação. Bom para performance.
- **Gráfico de candlestick manual:** Não usa `mplfinance` — implementação própria com `ax.bar()` e `ax.plot()` para OHLC. Mais controle sobre estilo mas mais código.
- **Hover via `mpl_connect('motion_notify_event')`:** Tooltip interativo que segue o mouse — recurso avançado do Matplotlib.
- **Cores Bloomberg-style:** Fundo escuro (`#0d0d0d`), texto cinza (`#c0c0c0`), verde/vermelho para candles, azul para vol.
- **Bandas de sigma:** Calculadas com `np.diff(np.log(prices))` para retornos logarítmicos, depois `sigma_daily = np.std(log_ret)` e `sigma_periodo = sigma_daily * sqrt(n_sessoes)`.
