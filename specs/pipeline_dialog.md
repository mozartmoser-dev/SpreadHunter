# PipelineDialog

## Propósito

Diálogo de visualização de pipeline de processamento — estilo Bloomberg. Exibe tabela horizontal com 7 colunas (ESTÁGIO, TOTAL, APROVADOS, REJEITADOS, %, PROGRESSO, DURAÇÃO) para cada estágio do `PipelineTracker`. Barras de progresso customizadas (`_BarWidget`) com gradiente azul. Suporta clique para detalhes do estágio e cópia de texto formatado.

## Contrato (Requisitos)

### `__init__(tracker: PipelineTracker | None, parent)`
**Garante:**
1. Se `tracker` é None ou não tem stages, exibe mensagem "Nenhum dado de pipeline disponível".
2. Título: "Pipeline: {tracker.nome_estrategia}".
3. Tabela com 7 colunas e uma linha por estágio.
4. Footer: total de viáveis + percentual de aprovação.

### `_BarWidget`
**Garante:**
1. Barra de progresso horizontal (110×18px) pintada com `QPainter`.
2. Fundo escuro com borda arredondada.
3. Barra preenchida com gradiente linear azul (`#4fc3f7` → lighter 130%).
4. Largura proporcional ao `pct` (0.0–1.0).

### Colunas da tabela
**Garante:**
1. **ESTÁGIO:** Nome do estágio (string).
2. **TOTAL:** Entrada (`s.entrada`, formatado com separador de milhar ".").
3. **APROVADOS:** Saída (`s.saida`) em verde.
4. **REJEITADOS:** `entrada - saida` em vermelho (se > 0) ou cinza.
5. **%:** Percentual de aprovação do estágio (`saida/entrada * 100`).
6. **PROGRESSO:** `_BarWidget` com `pct_geral = saida / max_entrada`.
7. **DURAÇÃO:** Tempo formatado (`s.tempo_s`) — µs, ms ou s.

### `_on_cell_clicked(row, col)`
**Garante:**
1. Exibe tooltip com detalhes do estágio: nome, entrada, saída, rejeitados, percentual, duração, mensagem descritiva (se disponível no `PipelineTracker.stages[row]`).

### `_fmt_tempo(segundos)`
**Garante:**
1. < 0.001s: microssegundos (µs).
2. < 1.0s: milissegundos (ms).
3. ≥ 1.0s: segundos com 2 casas decimais.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QToolTip` | UI framework |
| `PySide6.QtCore` | `Qt, QRectF, QPoint, QTimer` | Geometria |
| `PySide6.QtGui` | `QPainter, QColor, QPen, QFont, QBrush, QLinearGradient, QGuiApplication` | Renderização |
| `src.domain.services.pipeline_tracker` | `PipelineTracker` | Dados do pipeline |

## Métricas

| Linhas | 223 |
| Classes | 2 (`_BarWidget`, `PipelineDialog`) |
| Testes | Não |

## Notas

- **Estilo Bloomberg:** Paleta de cores hardcoded no módulo (`_BG = "#0d0d1a"`, `_HDR_FG = "#ffd740"`, etc.) — consistente com o tema dark do app.
- **Formatação numérica:** `_fmt(n)` usa separador de milhar "." (estilo europeu) via `f"{n:,}".replace(",", ".")`.
- **Aberto via `Ctrl+Shift+F`:** Shortcut global registrado na `MainWindow` que chama `_abrir_pipeline()`.
- **Snapshots de pipeline:** A `MainWindow` armazena `_pipeline_monitor`, `_pipeline_vendidas`, `_pipeline_coberta` após cada ciclo do worker, mas apenas o pipeline do monitor principal é exibido por padrão.
