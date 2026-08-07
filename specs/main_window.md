# MainWindow

## Propósito

Janela principal do Spreadhunter — QMainWindow que orquestra toda a UI. Contém 3 tabelas de monitor (Oportunidades, Vendidas, Venda Coberta) em QSplitter vertical, barra de ferramentas com botões de estratégias (Colar, Collar Calendário, Box 4P, Put Ratio, MPP), dropups de painéis e ferramentas, controles de Top-N, sinos de alerta sonoro, splash screen com fade e disclaimer. Conecta-se ao `MonitorWorker` (QThread) via sinais para receber atualizações de todas as estratégias.

## Contrato (Requisitos)

### `__init__(self, db_path=None)`
**Garante:**
1. Cria `MonitorWorker` com o `db_path` e conecta 12 sinais (`oportunidades_atualizadas`, `vendidas`, `coberta`, `colares`, `colares_calendario`, `boxes`, `put_ratio`, `mpp`, `mre`, `status_message`, `rtd_status`, `engine_stats_updated`, `mpp_status_changed`, `integridade_params_verificada`).
2. Configura splash screen com vídeo MP4, GIF animado ou JPEG estático (fallback: texto "SPREADHUNTER").
3. Exibe transição com fade-out e tela de disclaimer antes de mostrar as tabelas.
4. Shortcuts globais: `Ctrl+Shift+F` (Pipeline), `Ctrl+=/+` (aumentar fonte), `Ctrl+-` (diminuir fonte), `Ctrl+0` (resetar fonte), `Alt+C` (Calculadoras).
5. Timer de 1s para atualizar status de scan (`_update_scan_status`).

### Gerenciamento de tabelas
**Garante:**
1. Três `QTableView` com modelos próprios (`MonitorTableModel`, `VendidasTableModel`, `VendaCobertaTableModel`) cada um com `TopNSortProxy`.
2. Persistência de ordem/largura de colunas via `column_utils` (QSettings) para cada tabela.
3. Esconde colunas default via `HIDDEN_BY_DEFAULT` de cada modelo.
4. `BadgeDelegate` aplicado às colunas `label_tipo` e `liq_indicator` da tabela principal.
5. Filtro de vencimento por tabela (`_filtro_vencimento`, `_filtro_vencimento_vendidas`, `_filtro_vencimento_coberta`).
6. Controle de foco: ao clicar em uma tabela, `_foco_vendidas`/`_foco_coberta` são atualizados — usado para determinar qual tabela exportar.

### Controles da barra inferior
**Garante:**
1. Botão "Ligar"/"Parar" (`btn_varrer`) — alterna `MonitorWorker.start()` / `stop()`.
2. Sinos de alerta: global (`btn_bell`), vendidas (`btn_bell_v`), coberta (`btn_bell_c`) — cada um com toggle visual (vermelho/verde) e estado persistido em `_som_*_ativado`.
3. Exportação CSV individual por tabela (botões 📥) com suporte a seleção de linha (exporta só a selecionada) ou todas.
4. Controles Top-N (`_spin_topn_box`, `_spin_topn_vend`) com botões +/- e label de valor.
5. Checkbox "Exibir Todas" (`chk_tp_op`) que controla `_mostrar_tp_op` no worker — quando desmarcado, filtra classificações "TP.Op" e não-viaveis.

### Dropup "Painéis"
**Garante:**
1. Menu QToolButton com 8 ações: Grade de Opções, Histórico Operações, Proventos, Agenda de Balanços, Feriados, Estudos Calendário, Taxa Aluguel, Atualizar Tudo.
2. `_BtnProxy` — adaptador que preserva API `self.btn_*` legada (`.setEnabled()`, `.setText()`, `.setVisible()`) mapeando para QActions do menu.
3. Menu abre para cima (dropup) via `mapToGlobal` + `sizeHint`.

### Dropup "Ferramentas"
**Garante:**
1. 4 ações: Calculadoras (`Alt+C`), Workspace, Histórico de Simulações, Verificar Integridade dos Parâmetros.
2. Separadores entre grupos lógicos.

### Integridade de parâmetros (`_verificar_integridade_sob_demanda`)
**Garante:**
1. Importa dinamicamente `scripts.verificar_integridade_params.verificar`.
2. Exibe divergências (hardcoded vs banco vs JSON) em QMessageBox.
3. Se nenhuma divergência, exibe "Nenhuma divergência encontrada".

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `sys` | stdlib | `_MEIPASS` (PyInstaller path) |
| `collections` | `Counter` | (não localizado no uso direto) |
| `datetime` | `datetime, date, timedelta` | Filtros de vencimento |
| `functools` | `partial` | Conexões lambda |
| `pathlib` | `Path` | Paths de assets (temas/) |
| `PySide6.QtWidgets` | `QMainWindow, QWidget, ...` | UI framework |
| `PySide6.QtCore` | `Qt, QTimer, QSize, ...` | Sinais, timers, animações |
| `PySide6.QtMultimedia` | `QMediaPlayer` | Splash video MP4 |
| `PySide6.QtMultimediaWidgets` | `QVideoWidget` | Splash video widget |
| `PySide6.QtGui` | `QFont, QColor, QBrush, QIcon, QPixmap, QPainter, QAction, QShortcut, QKeySequence, QMovie` | Renderização e shortcuts |
| `src.infrastructure.persistence.database` | `get_db_path` | Path default do banco |
| `src.application.use_cases.exportar_operacao` | `ExportarOperacaoUseCase` | Exportação de operações |
| `src.ui.desktop.theme` | `DARK_THEME_QSS, Palette, get_theme_qss` | Tema dark |
| `src.ui.desktop.monitor_table_model` | `MonitorTableModel` | Modelo da tabela principal |
| `src.ui.desktop.vendidas_table_model` | `VendidasTableModel` | Modelo da tabela de vendidas |
| `src.ui.desktop.venda_coberta_table_model` | `VendaCobertaTableModel` | Modelo da tabela de venda coberta |
| `src.ui.desktop.monitor_worker` | `MonitorWorker` | Thread de varredura |
| `src.ui.desktop.export_dialog` | `ExportDialog` | Diálogo de exportação |
| `src.ui.desktop.parametros_widget` | `ParametrosWidget` | Widget de parâmetros |
| `src.ui.desktop.engine_dashboard` | `EngineDashboard` | Dashboard de engine |
| `src.ui.desktop.sensibilidade_mercado_widget` | `SensibilidadeMercadoWidget` | Widget de sensibilidade |
| `src.ui.desktop.colar_dialog` | `ColarDialog` | Diálogo de colar |
| `src.ui.desktop.colar_calendario_dialog` | `ColarCalendarioDialog` | Diálogo de colar calendário |
| `src.ui.desktop.box_dialog` | `BoxDialog` | Diálogo de box |
| `src.ui.desktop.mpp_dialog` | `MppDialog` | Diálogo de MPP |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Leitura de parâmetros |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência de colunas |
| `src.ui.desktop.mercado_topbar` | `MercadoTopBarWidget` | Barra de topo com dados de mercado |

## Métricas

| Linhas | 2557 |
| Classes | 2 (`TopNSortProxy`, `MainWindow`) + 2 internas (`_BtnProxy`, `_FonteWheelFilter`) |
| Testes | Parcial (testado indiretamente via `test_fase3.py`; sem testes unitários isolados para MainWindow) |

## Notas

- **Segfault ao arrastar coluna:** Handlers `sectionMoved` e `sectionResized` usam `QTimer.singleShot(0, lambda: ...)` para evitar conflito com `layoutChanged` durante sort (regra AGENTS.md).
- **`beginResetModel()`/`endResetModel()`:** As tabelas não usam — os modelos usam `layoutAboutToBeChanged`/`layoutChanged` (monitor) e `beginResetModel`/`endResetModel` (vendidas/coberta). `sectionsMovable` e `blockSignals` não são usados explicitamente na MainWindow, apenas nos modelos.
- **Splash screen em 4 estágios:** Abertura (MP4/GIF/JPG) → Transição (fade-out 800ms) → Disclaimer (clique para fechar) → Splitter (tabelas). `QStackedWidget` gerencia a transição.
- **`_aplicar_tema_configurado()`** — chamado no construtor, lê tema do banco (claro/escuro). Não encontrado nos imports visíveis — provavelmente método interno que usa `get_theme_qss`.
- **`mousePressEvent` override nas tabelas:** Técnica de lambda com tupla `(setattr(...), setattr(...), QTableView.mousePressEvent(...))[2]` — hack para capturar foco da tabela sem perder o comportamento original. POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: se o garbage collector limpar a tupla, o índice `[2]` pode falhar.
- **Controle de fonte com Ctrl+Scroll:** `_FonteWheelFilter` instalado como event filter nas 3 tabelas. Usa `_ajustar_fonte(delta)` com limite de 7 a 14 pontos.
