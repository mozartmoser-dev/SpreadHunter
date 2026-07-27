# Graph Report - Spreadhunter  (2026-07-07)

## Corpus Check
- 167 files · ~879,535 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2021 nodes · 5085 edges · 146 communities (108 shown, 38 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 953 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `75d6f404`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Options Pricing Calculator
- Opportunity Classification Logic
- Asynchronous Tail Monitoring
- OpenFast Socket Adapter
- PETR4 Intraday Monitoring
- Market Data Source Interface
- Database Migration Management
- Collar Strategy Dialog
- MPP Strategy Use Case
- MPP Table Model
- Trading Domain Enums
- B3 Holiday Management
- Instrument Data Repository
- Dividend Data Provider
- Main Application Window
- Market Data Provider
- Box Strategy Dialog
- Collar Calendar Dialog
- Monitor Table Model
- UI Settings Persistence
- OpcoesNet API Client
- Operation Export Use Case
- Stock Rental Rate Collection
- Earnings Calendar Provider
- Market Data Mocking
- Collar Calendar Monitoring
- Operational Parameter Repository
- PNT Automation Interface
- Earnings Calendar Repository
- OpenFast Performance Testing
- Export Configuration Dialog
- Trading Strategy Calculators
- Opportunity Monitor Display
- Sold Opportunity Model
- Table Cell Display Logic
- Market Data Adapter Tests
- Covered Call Model
- Trade History Dialog
- Opportunity Monitoring Service
- MPP and Rules Dialogs
- Collar Strategy Monitoring
- Payoff Visualization Dialog
- UI Styling and Delegates
- Telegram Notification Service
- B3 Transaction Cost Calculator
- PNT Automation Utilities
- Collar Calendar Table Model
- Engine Performance Dashboard
- PNT Integration Service
- Collar Strategy Calculator
- FastTrade Server Mock
- Audio Notification Service
- Parameters Configuration Widget
- Box Strategy Monitoring
- PNT Screen Management
- Strategy Explanation Dialog
- Application Entry Point
- CDI Interest Calculator
- Covered Call Monitoring
- Sold Strategy Monitoring
- CVM Earnings Provider
- Blacklist Management Dialog
- Whitelist Management Dialog
- Opportunity Monitor Tests
- Box Strategy Table Model
- CDI Calculator Dialog
- Box Strategy Calculator
- Scan Performance Diagnostics
- Socket Connection Diagnostics
- Project Dependencies
- Graph Visualization Plugin
- UI Automation Testing
- Application Branding Assets
- Build Runtime Hooks
- Market Data Configuration
- Spread Coefficient Calculator
- UI Preview Toolbar
- Liquidity Indicator Logic
- Main Application Package
- API Discovery Utility
- Tool UI Labels
- Large Tool Icons
- Standard Tool Icons
- Basket Order Import
- Directional Robot UI
- Order Type Labels
- Order Type Headers
- Performance Engine Icons
- Prompt: Correção PNT Automation (SwitchToThisWindow + acento)
- GradeOpcoesDialog
- .__init__
- Sessão 24/06/2026 — Correções Deploy + RTD Estável
- TaxaAluguelDialog
- SKILL.md
- calculadora_vetorizada.py
- Automação Basket PNT — instruções de uso
- MockMarketDataProvider
- Sessão 26/06/2026 — Chave Composta (Layer 4) + Correção Cruzamento Ativos
- Spreadhunter
- Prompt para Gemini — Diagnóstico da automação PNT
- Sessão 07/07/2026 — Estratégias Vendidas (TAXA / BOX Vendida / SBTH Vendida)
- Sessão 07/07/2026 (parte 4) — Refatoração ParametrosWidget (Sidebar + Stack)
- Sessão 09/06/2026 — Correções Estruturais + Performance
- MonitorColaresCalendarioUseCase
- Sessão 11/06/2026 (parte 4) — Crash ao Arrastar Coluna (Segfault C++)
- Sessão 11/06/2026 (parte 2) — MOD fix + Cleanup + Blacklist
- Sessão 07/07/2026 (parte 5) — Guia do Amigo (Diagnóstico via dev)
- Sessão 11/06/2026 (parte 3) — RTD Timeout + COM Thread Safety + Blacklist Final
- Sessão 11/06/2026 — API OptionsChain + Semanais + Crash Fix
- opencode.json
- OPCOES_DROPDOWN.md
- ._on_importflash_concluido

## God Nodes (most connected - your core abstractions)
1. `ParametroRepository` - 153 edges
2. `MainWindow` - 118 edges
3. `InstrumentoRepository` - 114 edges
4. `OpenFastSocketAdapter` - 84 edges
5. `InstrumentoOpcional` - 71 edges
6. `Palette` - 67 edges
7. `get_connection()` - 64 edges
8. `MonitorWorker` - 64 edges
9. `MonitorTableModel` - 63 edges
10. `CalculadoraColarCalendario` - 59 edges

## Surprising Connections (you probably didn't know these)
- `_FiltroManutencao` --uses--> `MainWindow`  [INFERRED]
  main.py → src/ui/desktop/main_window.py
- `TestExportarOperacaoUseCase` --uses--> `OportunidadeMonitor`  [INFERRED]
  tests/test_fase3.py → src/application/dtos/dtos.py
- `TestMonitorOportunidadesUseCase` --uses--> `OportunidadeMonitor`  [INFERRED]
  tests/test_fase3.py → src/application/dtos/dtos.py
- `TestDadosRTDInstrumento` --uses--> `OportunidadeMonitor`  [INFERRED]
  tests/test_fase4.py → src/application/dtos/dtos.py
- `TestMockMarketDataProvider` --uses--> `OportunidadeMonitor`  [INFERRED]
  tests/test_fase4.py → src/application/dtos/dtos.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Toolbar UI Design Proposals** — temas_preview_toolbar, temas_preview_toolbar_vazado [EXTRACTED 1.00]

## Communities (146 total, 38 thin omitted)

### Community 0 - "Options Pricing Calculator"
Cohesion: 0.05
Nodes (18): CalculadoraColarCalendario, date, ResultadoColarCalendario, TipoColarCalendario, TestBlackScholes, TestBsTheta, TestCalcular, TestCalcularCdiPeriodo (+10 more)

### Community 1 - "Opportunity Classification Logic"
Cohesion: 0.05
Nodes (17): Oportunidade, ClassificacaoOportunidade, CalculadoraBoxSbth, DadosMercado, ResultadoBOXSBTH, CandidatoPescaria, ElegibilidadePescaria, extrair_strike() (+9 more)

### Community 2 - "Asynchronous Tail Monitoring"
Cohesion: 0.14
Nodes (6): CalculadoraCaudaAssincrona, Pós-processa um ResultadoColarCalendario viável e calcula o ratio     ótimo de C, ResultadoCaudaAssincrona, Tests for CalculadoraCaudaAssincrona — the cauda ratio optimizer., Cenário típico: CALL OTM, gap > 0, encontra N ótimo com BE >= 3σ., TestCaudaBasics

### Community 3 - "OpenFast Socket Adapter"
Cohesion: 0.08
Nodes (5): OpenFastSocketAdapter, TestOpenFastSocketAdapterCache, TestOpenFastSocketAdapterConecta, TestOpenFastSocketAdapterDirtyKeys, TestOpenFastSocketAdapterRegistrar

### Community 4 - "PETR4 Intraday Monitoring"
Cohesion: 0.06
Nodes (12): Analise PETR4 com pivot points + suportes intraday via API + RTD., Monitor PETR4 — updates de 1 em 1 minuto, Monitor PETR4 — análise a cada 2 min com projecoes, Monitora PETR4 spot + OTM 38.36 por 5 min, Monitor contínuo do book PETR4 com análise de direção + volume., Monitor bounce PETR4 — analise a cada 30 segundos, Monitor PETR4 a cada 20s — divergencias + bounce, Script para ler PETR4 do Profit RTD e calcular Put Ratio Spread. (+4 more)

### Community 5 - "Market Data Source Interface"
Cohesion: 0.10
Nodes (7): Protocol, FieldName, MarketDataSource, Traduz FieldName → str Profit. RTDProfit permanece intacto., RTDProfitAdapter, adapter(), RTDProfitAdapter com RTDProfit mockado.

### Community 6 - "Database Migration Management"
Cohesion: 0.11
Nodes (20): Connection, Testa migração de fonte_market_data 0/1 → profit/openfast., ImportFlash: varre opcoes.net.br e atualiza o banco do SpreadHunter.  Captura o, _get_appdata_dir(), get_db_path(), init_db(), _migrar_banco_legado(), _migrar_calendario_resultados() (+12 more)

### Community 7 - "Collar Strategy Dialog"
Cohesion: 0.07
Nodes (9): QListWidget, ColarDialog, ColarSortProxy, ColarTableModel, ler_whitelist_colar(), atualizar_resultados must restore header movable/blocked state after update., atualizar must wrap item replacement in beginResetModel/endResetModel., test_atualizar_resultados_header_freeze_restore() (+1 more)

### Community 8 - "MPP Strategy Use Case"
Cohesion: 0.09
Nodes (9): BoxScore, MPPUseCase, MreResultado, date, Persiste spread history em batch — chamado no final do ciclo MPP., MercadoEstruturalProvider, date, _mpp_model() (+1 more)

### Community 9 - "MPP Table Model"
Cohesion: 0.07
Nodes (29): ResultadoBox, MppTableModel, _box_col_key(), _col_key(), _make_full_opp(), Tests that display formatting matches calculation in all 3 strategy dialogs.  If, Each ColarTableModel column must format its value correctly., Each ColarCalTableModel column must format its value correctly. (+21 more)

### Community 10 - "Trading Domain Enums"
Cohesion: 0.12
Nodes (26): Enum, ExportarResultado, TipoExportacao, ExportarOperacaoUseCase, EstruturaOperacional, TipoEstrutura, ClassificacaoOp, Lado (+18 more)

### Community 11 - "B3 Holiday Management"
Cohesion: 0.08
Nodes (7): FeriadoB3Repository, FeriadosB3Provider, B3 fecha em 9 de Julho (Revolução Constitucionalista - feriado SP)., FeriadosDialog, FeriadosFetchWorker, FeriadosSortProxy, FeriadosTableModel

### Community 12 - "Instrument Data Repository"
Cohesion: 0.07
Nodes (16): Row, InstrumentoOpcional, InstrumentoRepository, _parse_date(), date, Retorna dicionário {(ativo, cod_put): InstrumentoOpcional}.         Chave compo, Safely extract strike column (may not exist in legacy DB)., _row_strike() (+8 more)

### Community 13 - "Dividend Data Provider"
Cohesion: 0.11
Nodes (4): DividendosStatusInvestProvider, DividendosDialog, DividendosFetchWorker, DividendosTableModel

### Community 15 - "Market Data Provider"
Cohesion: 0.10
Nodes (8): MercadoDataProvider, Registra apenas os ativos (underlyings) para obter preços de referência rápido., Registra todos os campos de um instrumento quando detectamos liquidez., Detecta novos books, registra Onda 2, background scan e salva prioridades., Retorna contagens internas para o Dashboard de Performance., Limpa as flags de cache e força o re-registro dos instrumentos no RTD., Open Fast nao usa CAB skip — suporta_cab_skip=False., TestMercadoProviderOpenFast

### Community 16 - "Box Strategy Dialog"
Cohesion: 0.08
Nodes (7): BoletaDialog, BoxDialog, BoxSortProxy, BoxTableModel, Alerta se algum ativo nos resultados está em dia ex de dividendo., PipelineDialog, Diálogo de pipeline estilo Bloomberg (tabela horizontal com barras).

### Community 17 - "Collar Calendar Dialog"
Cohesion: 0.10
Nodes (5): QAbstractTableModel, QListWidgetItem, ColarCalSortProxy, ColarCalTableModel, ler_whitelist_colar_calendario()

### Community 18 - "Monitor Table Model"
Cohesion: 0.16
Nodes (3): MonitorTableModel, _make_opp(), TestMonitorTableModel

### Community 19 - "UI Settings Persistence"
Cohesion: 0.09
Nodes (24): QSettings, QSortFilterProxyModel, tocar(), CalculadorasDialog, Calculadoras — diálogo unificado com abas Black-Scholes e CDI.  A aba B&S mantém, Diálogo com abas B&S e CDI. Substitui btn_calc + btn_cdi., CalendarioSortProxy, restaurar_ordem_colunas() (+16 more)

### Community 20 - "OpcoesNet API Client"
Cohesion: 0.12
Nodes (8): Session, OpcoesNetClient, Busca grade de opções (strike x vencimento) do opcoes.net.br.         tipo: 'CAL, Busca o mapping {ticker: 'A'/'E'} (MOD = modelo Americano/Europeu)         via A, Retorna lista de todos os ativos com opções disponíveis em opcoes.net.br., Busca todas as opções (CALL + PUT) de um ativo via API, incluindo         séries, Busca histórico de candles + volatilidade do ativo via API.         Request type, Retorna lista de candles {date, open, high, low, close, change, volume, vol_hist

### Community 21 - "Operation Export Use Case"
Cohesion: 0.19
Nodes (9): datetime, BasketGerada, ImportarResultado, PernaImediata, TipoOpcao, RiscoLeilao, TipoColar, _parse_datetime() (+1 more)

### Community 22 - "Stock Rental Rate Collection"
Cohesion: 0.17
Nodes (7): ColetarTaxasAluguelUseCase, TaxaAluguel, InvestSiteClient, TaxaAluguelRepository, TestColetarTaxasAluguelUseCase, TestInvestSiteClient, TestTaxaAluguelRepository

### Community 23 - "Earnings Calendar Provider"
Cohesion: 0.11
Nodes (4): CalendarioResultadosWebwalletProvider, CalendarioFetchWorker, CalendarioResultadosDialog, CalendarioTableModel

### Community 25 - "Collar Calendar Monitoring"
Cohesion: 0.22
Nodes (3): PipelineStage, PipelineTracker, Coleta dados do pipeline de filtros sem afetar a execução.      Uso:         tra

### Community 26 - "Operational Parameter Repository"
Cohesion: 0.16
Nodes (9): ParametroOperacional, ParametroRepository, ler_blacklist(), salvar_blacklist(), ler_whitelist(), salvar_whitelist(), parametro_repo(), db_path() (+1 more)

### Community 27 - "PNT Automation Interface"
Cohesion: 0.10
Nodes (24): _achar_combobox(), _achar_janela_pnt(), _debug_screenshot(), _diagnostic_list_windows(), executar_automacao_pnt(), PNT UI Debug Screenshot, PNT UI Debug Step 4, PNT UI Debug Step 5 (+16 more)

### Community 28 - "Earnings Calendar Repository"
Cohesion: 0.15
Nodes (3): get_connection(), CalendarioResultadosRepository, DividendoRepository

### Community 29 - "OpenFast Performance Testing"
Cohesion: 0.12
Nodes (11): LoadSimulator, socket, Teste de performance da _thread_leitora do OpenFastSocketAdapter.  Simula o serv, Espera a thread leitora processar N atualizações no cache., Mede quão rápido a thread leitora processa dados em lote., Mede o custo do parse + batch mutex (nova abordagem)., Simula contenção: thread leitora + main thread lendo cache., Servidor que simula o fasttrader enviando push para N instrumentos. (+3 more)

### Community 30 - "Export Configuration Dialog"
Cohesion: 0.18
Nodes (6): QLabel, ExportDialog, QFrame, QWidget, Aciona a integração visual com o PNT com feedback de progresso., Nível 3: Alerta se o ativo estiver em dia ex de dividendo hoje.

### Community 31 - "Trading Strategy Calculators"
Cohesion: 0.29
Nodes (8): atualizar_calendario(), dc_to_du(), dc_to_du_aproximado(), dc_to_du_exato(), eh_feriado(), frac_du(), date, _reconstruir_calendario()

### Community 32 - "Opportunity Monitor Display"
Cohesion: 0.12
Nodes (4): OportunidadeMonitor, monitor_uc(), test_mensagem_telegram_pct_ganho_box_formatado_corretamente(), test_mensagem_telegram_pct_ganho_formatado_corretamente()

### Community 34 - "Table Cell Display Logic"
Cohesion: 0.14
Nodes (20): _monitor_col_key(), _monitor_opp(), MonitorTableModel cell display for BOX strategy., ganho_display must use percent_sbth for SBTH classification., ganho_display must use max(ganho_box, ganho_sbth) for BOX+SBTH., ganho_display must use sbth for 2SBTH regardless of box value., ganho_display must show '-' when both percentages are zero., tipo_opcao mapping: A→AMER, E→EUR, P→PUT. (+12 more)

### Community 38 - "Opportunity Monitoring Service"
Cohesion: 0.24
Nodes (3): MonitorOportunidadesUseCase, monitor_uc(), TestMonitorOportunidadesUseCase

### Community 40 - "Collar Strategy Monitoring"
Cohesion: 0.29
Nodes (4): MonitorColaresUseCase, ResultadoColar, atualizar_resultados dict building must match expected arithmetic., test_colar_derived_values()

### Community 41 - "Payoff Visualization Dialog"
Cohesion: 0.12
Nodes (10): QDialog, QTextEdit, ColarCalendarioDialog, copiar_figura_clipboard(), copiar_texto_formatado(), Renderiza matplotlib Figure para PNG e cola como imagem no clipboard., Salva matplotlib Figure como PNG via diálogo., Copia conteúdo do QTextEdit como HTML + plain text para o clipboard. (+2 more)

### Community 42 - "UI Styling and Delegates"
Cohesion: 0.17
Nodes (5): QStyledItemDelegate, QToolButton, BadgeDelegate, QIcon, Constrói o botão 🗂 Painéis que abre um dropup QMenu com os 7 dialogs.

### Community 43 - "Telegram Notification Service"
Cohesion: 0.21
Nodes (4): TelegramNotifier, Fetch token, chat_id and enable flag from the parameters table.         Returns, Facade that reads telegram configuration from the DB and sends messages.     It, TelegramService

### Community 44 - "B3 Transaction Cost Calculator"
Cohesion: 0.15
Nodes (6): DadosPata, CalculadoraCustosB3, Taxa total para opções (emol + liq + reg + iss)., Taxa total para ações (emol + liq + iss — sem registro)., Custo B3 para opções: taxa_total × prêmio médio × pernas × (2 se ida_e_volta)., Custo B3 para ações: taxa_total_stock × preço × ações × (2 se ida_e_volta).

### Community 45 - "PNT Automation Utilities"
Cohesion: 0.11
Nodes (13): _achar_janela_pnt_por_processo(), _focar_janela_pnt(), PNTScreenManager, Localiza HWND do PNT pelo nome do processo PnT.Inteface.exe., Gerenciador de telas do PNT via reconhecimento de imagem, Encontra e foca a janela do PNT usando Win32 API (ou fallback pyautogui)., Localiza e ativa a janela do PNT: processo > título., Abre a tela MultiLeg manualmente (usuário deve fazer isso) (+5 more)

### Community 47 - "Engine Performance Dashboard"
Cohesion: 0.31
Nodes (4): QFrame, EngineStatsDTO, EngineDashboard, StatCard

### Community 48 - "PNT Integration Service"
Cohesion: 0.19
Nodes (6): PNTIntegration, Integração com PlugNTrade via automação de interface (GUI) usando Clipboard., Busca parâmetros operacionais no banco de dados., Limpa o campo atual e digita o valor formatado (ponto para vírgula)., Monta dados no formato de importação direcional do PlugNTrade., Envia a oportunidade usando o fluxo correto de importação do PNT.

### Community 51 - "FastTrade Server Mock"
Cohesion: 0.11
Nodes (10): MockFastTradeServer, socket, Simula chegada de SQT., Servidor TCP fake que emula Open Fast. Porta 5557 para não conflitar., server(), Adapter tambem aceita # como separador., server(), TestOpenFastSocketAdapterReconexao (+2 more)

### Community 52 - "Audio Notification Service"
Cohesion: 0.45
Nodes (10): Path, _carregar_params(), _gerar_wav_volume(), testar(), testar_coberta(), testar_vendidas(), tocar_coberta(), _tocar_premio() (+2 more)

### Community 53 - "Parameters Configuration Widget"
Cohesion: 0.08
Nodes (13): QComboBox, QDoubleSpinBox, QWidget, BlackScholesWidget, _brl(), CdiWidget, Lê ParametroRepository.get_by_chave('taxa_cdi'); fallback = JSON default., Formata float no padrão BR: 1.234,56. (+5 more)

### Community 55 - "PNT Screen Management"
Cohesion: 0.14
Nodes (3): criar_data_source(), TestDataSourceFactory, TestFieldNameEnum

### Community 56 - "Strategy Explanation Dialog"
Cohesion: 0.22
Nodes (16): QPainter, QPixmap, _clip_rounded(), _flag_icon(), _hex(), _pixmap_br(), _pixmap_eu(), _pixmap_us() (+8 more)

### Community 57 - "Application Entry Point"
Cohesion: 0.33
Nodes (5): _clear_pycache(), _FiltroManutencao, run_app(), carregar_do_banco(), bootstrap()

### Community 58 - "CDI Interest Calculator"
Cohesion: 0.13
Nodes (14): Auto-documentação dos Filtros nas Regras, Fixes aplicados, Horário do Mercado, Lição Aprendida — Strike via Sufixo do Código B3, MOD (tipo_opcao) — Só da CALL, Parametrização Obrigatória, Pendência — Validação do calendário de DU no Black-Scholes, Regras de Negócio (+6 more)

### Community 62 - "Blacklist Management Dialog"
Cohesion: 0.18
Nodes (6): QThread, main(), BlacklistImportDialog, _ImportThread, Roda importflash.main() capturando stdout/stderr linha a linha., Botão Atualizar: abre blacklist dialog e dispara importação.

### Community 65 - "Box Strategy Table Model"
Cohesion: 0.14
Nodes (13): Arquivos Relacionados, Automação — `executar_automacao_pnt()`, Diferenças entre nosso formato e o oficial:, Direcional — Formato (sem automação), Exemplo MultiLeg com Opções Mensais PETR4, Importação de Ordens no PNT (FastTrader), Linha de exemplo copiável (3 pernas, mensal jun/26):, MultiLeg — Formato Oficial PNT (10 colunas para 3 pernas) (+5 more)

### Community 66 - "CDI Calculator Dialog"
Cohesion: 0.15
Nodes (12): Arquivos de build, Build, Cuidados, Distribuição — Build PyInstaller, Fluxo de distribuição, Histórico, O que o script faz, O que o script **NÃO** faz mais (+4 more)

### Community 70 - "Socket Connection Diagnostics"
Cohesion: 0.19
Nodes (9): QColor, QTreeWidgetItem, _dias_ate(), _fmt_strike(), _label_serie(), date, Gera label amigável: 'SEMANA 2 — 10/07/2026' ou 'MENSAL — 21/08/2026'., Retorna o created_at mais recente entre os instrumentos. (+1 more)

### Community 73 - "UI Automation Testing"
Cohesion: 0.21
Nodes (3): _int_param(), copiar_basket_pnt(), fmt_br()

### Community 74 - "Application Branding Assets"
Cohesion: 0.67
Nodes (3): Spreadhunter Disclaimer, Spreadhunter Opening Theme, Spreadhunter Initializing Theme

### Community 77 - "Spread Coefficient Calculator"
Cohesion: 0.17
Nodes (11): Algoritmo Central (determinístico, sem loop), Arquitetura Atual (Colar Calendário Coberto — Existente), Chassis Yang Xu (Seção 2 do documento) → Define σ para o cálculo de K_3σ, Collar Calendário Estrutural Calda Assíncrona, Integração sem Tocar no Fluxo Existente, Modelo de Dados — ResultadoCaudaAssincrona (Novo DTO), Nova Especificação — Correção de Leitura, Observações (+3 more)

### Community 88 - "API Discovery Utility"
Cohesion: 0.17
Nodes (11): 1. Remover "PnT" e "Profit" das listas (linhas 20, 103-112, 114-123), 2. Adicionar `_achar_janela_pnt_por_processo()` (após `_achar_janela_pnt()`, linha 160), 3. Modificar `_focar_janela_pnt()` (linhas 284-320), 4. Modificar `_obter_rect_pnt()` (linhas 323-343), Adicionar teste para busca por processo, Arquivo, Arquivo de teste, Atualizar teste `test_switchtothiswindow_usado` (+3 more)

### Community 121 - "Prompt: Correção PNT Automation (SwitchToThisWindow + acento)"
Cohesion: 0.20
Nodes (9): Arquivo: `src/infrastructure/integrations/pnt.py`, Como testar, Contexto, Correções necessárias (SOMENTE 3 linhas), Fluxo esperado após a correção, Notas importantes, O que NÃO está quebrado (não mexer), Prompt: Correção PNT Automation (SwitchToThisWindow + acento) (+1 more)

### Community 122 - "GradeOpcoesDialog"
Cohesion: 0.27
Nodes (3): GradeOpcoesDialog, Diálogo visualizador da grade de opções estilo plataforma Profit., Recarrega a lista de ativos do banco e popula o combo.

### Community 123 - ".__init__"
Cohesion: 0.36
Nodes (5): _BarWidget, _fmt(), _fmt_tempo(), _mkitem(), Barra de progresso horizontal para a coluna PROGRESSO.

### Community 124 - "Sessão 24/06/2026 — Correções Deploy + RTD Estável"
Cohesion: 0.22
Nodes (9): Build e Deploy, Build — Hidden Imports obrigatórios no `.spec`, Database path (crítico para deploy), Erro `name 'logger' is not defined`, Import roda em QThread (não QProcess), importflash.py — path do banco, Observações importantes p/ sessões futuras, RTD não fica flickando ON/OFF (+1 more)

### Community 126 - "SKILL.md"
Cohesion: 0.25
Nodes (7): 17/06/2026 — 11 correções do novaavaliacao.md, Confirmação Obrigatória, Convenções de Código, Estrutura de Pastas, Histórico de Sessões, Regras de Negócio Críticas, Stack

### Community 127 - "calculadora_vetorizada.py"
Cohesion: 0.32
Nodes (5): CalculadoraVetorizada, ndarray, ResultadoVetorizado, dc_to_du_vetorizado(), ndarray

### Community 128 - "Automação Basket PNT — instruções de uso"
Cohesion: 0.25
Nodes (7): Automação Basket PNT — instruções de uso, Como testar, Dependências, Fluxo, Imagens necessárias, Integrar no clique do "📋 Basket PNT", Visão Geral

### Community 130 - "Sessão 26/06/2026 — Chave Composta (Layer 4) + Correção Cruzamento Ativos"
Cohesion: 0.29
Nodes (7): Arquivos alterados, Causa raiz, Correção — Chave Composta `(ativo, cod_opcao)`, Lições Aprendidas, Pendência, Problema, Sessão 26/06/2026 — Chave Composta (Layer 4) + Correção Cruzamento Ativos

### Community 131 - "Spreadhunter"
Cohesion: 0.29
Nodes (6): Confirmação Obrigatória, Convenções, Estrutura, Regras Críticas, Spreadhunter, Stack

### Community 132 - "Prompt para Gemini — Diagnóstico da automação PNT"
Cohesion: 0.29
Nodes (6): Anexos, Contexto, Código da função de seleção, Perguntas, Problema, Prompt para Gemini — Diagnóstico da automação PNT

### Community 133 - "Sessão 07/07/2026 — Estratégias Vendidas (TAXA / BOX Vendida / SBTH Vendida)"
Cohesion: 0.33
Nodes (6): Arquivos alterados, Definição (renomeada — "Venda Coberta" → **Taxa**), Parametrização, Rename cosmético (não renomeia classes/arquivos/chaves), Sessão 07/07/2026 — Estratégias Vendidas (TAXA / BOX Vendida / SBTH Vendida), Testes

### Community 134 - "Sessão 07/07/2026 (parte 4) — Refatoração ParametrosWidget (Sidebar + Stack)"
Cohesion: 0.33
Nodes (6): Arquivos alterados, Cobertura, Compatibilidade, Problema, Sessão 07/07/2026 (parte 4) — Refatoração ParametrosWidget (Sidebar + Stack), Solução — 4 tranches

### Community 135 - "Sessão 09/06/2026 — Correções Estruturais + Performance"
Cohesion: 0.33
Nodes (6): Book Detection, Carga Inteligente, Custos B3 (Crítico), Performance, Sessão 09/06/2026 — Correções Estruturais + Performance, UI

### Community 138 - "Sessão 11/06/2026 (parte 4) — Crash ao Arrastar Coluna (Segfault C++)"
Cohesion: 0.40
Nodes (5): Arquivos alterados, Causa, Correção, Sessão 11/06/2026 (parte 4) — Crash ao Arrastar Coluna (Segfault C++), Testes

### Community 139 - "Sessão 11/06/2026 (parte 2) — MOD fix + Cleanup + Blacklist"
Cohesion: 0.40
Nodes (5): Blacklist, Cleanup, Final, MOD fix no importflash, Sessão 11/06/2026 (parte 2) — MOD fix + Cleanup + Blacklist

### Community 140 - "Sessão 07/07/2026 (parte 5) — Guia do Amigo (Diagnóstico via dev)"
Cohesion: 0.50
Nodes (4): Arquivos auxiliares no projeto, Contexto, Sessão 07/07/2026 (parte 5) — Guia do Amigo (Diagnóstico via dev), Solução

### Community 141 - "Sessão 11/06/2026 (parte 3) — RTD Timeout + COM Thread Safety + Blacklist Final"
Cohesion: 0.50
Nodes (4): Blacklist sem preservação, Final, PERF-001: Rate Limiter no RTD RefreshData, Sessão 11/06/2026 (parte 3) — RTD Timeout + COM Thread Safety + Blacklist Final

### Community 142 - "Sessão 11/06/2026 — API OptionsChain + Semanais + Crash Fix"
Cohesion: 0.67
Nodes (3): Crash ao arrastar coluna, Semanais via API, Sessão 11/06/2026 — API OptionsChain + Semanais + Crash Fix

## Knowledge Gaps
- **143 isolated node(s):** `$schema`, `plugin`, `@opencode-ai/plugin`, `spreadhunter`, `ImportarResultado` (+138 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ParametroRepository` connect `Operational Parameter Repository` to `Opportunity Classification Logic`, `MockMarketDataProvider`, `Collar Strategy Dialog`, `MonitorColaresCalendarioUseCase`, `MPP Strategy Use Case`, `Trading Domain Enums`, `B3 Holiday Management`, `Instrument Data Repository`, `.__init__`, `Main Application Window`, `Market Data Provider`, `Box Strategy Dialog`, `Collar Calendar Dialog`, `Monitor Table Model`, `UI Settings Persistence`, `Operation Export Use Case`, `Stock Rental Rate Collection`, `Market Data Mocking`, `PNT Automation Interface`, `Opportunity Monitor Display`, `Opportunity Monitoring Service`, `MPP and Rules Dialogs`, `Collar Strategy Monitoring`, `Payoff Visualization Dialog`, `Telegram Notification Service`, `PNT Automation Utilities`, `Collar Calendar Table Model`, `PNT Integration Service`, `Audio Notification Service`, `Parameters Configuration Widget`, `Box Strategy Monitoring`, `Application Entry Point`, `Covered Call Monitoring`, `Sold Strategy Monitoring`, `Blacklist Management Dialog`, `Whitelist Management Dialog`, `Opportunity Monitor Tests`, `UI Automation Testing`, `.run`?**
  _High betweenness centrality (0.230) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `Main Application Window` to `Collar Strategy Dialog`, `.__init__`, `Trading Domain Enums`, `B3 Holiday Management`, `Instrument Data Repository`, `Dividend Data Provider`, `Box Strategy Dialog`, `._on_importflash_concluido`, `Monitor Table Model`, `UI Settings Persistence`, `OpcoesNet API Client`, `Operation Export Use Case`, `Stock Rental Rate Collection`, `Earnings Calendar Provider`, `Operational Parameter Repository`, `Earnings Calendar Repository`, `Export Configuration Dialog`, `Sold Opportunity Model`, `Covered Call Model`, `Trade History Dialog`, `MPP and Rules Dialogs`, `Payoff Visualization Dialog`, `UI Styling and Delegates`, `Collar Calendar Table Model`, `Engine Performance Dashboard`, `Strategy Filtering Logic`, `Parameters Configuration Widget`, `Application Entry Point`, `Market Scan Controls`, `GradeOpcoesDialog`, `TaxaAluguelDialog`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `InstrumentoRepository` connect `Instrument Data Repository` to `Opportunity Classification Logic`, `MockMarketDataProvider`, `Collar Strategy Dialog`, `MonitorColaresCalendarioUseCase`, `Trading Domain Enums`, `Dividend Data Provider`, `Main Application Window`, `Market Data Provider`, `Collar Calendar Dialog`, `Monitor Table Model`, `UI Settings Persistence`, `Operation Export Use Case`, `Stock Rental Rate Collection`, `Market Data Mocking`, `Operational Parameter Repository`, `Opportunity Monitoring Service`, `MPP and Rules Dialogs`, `Collar Strategy Monitoring`, `Payoff Visualization Dialog`, `Collar Calendar Table Model`, `Box Strategy Monitoring`, `Strategy Explanation Dialog`, `Covered Call Monitoring`, `Sold Strategy Monitoring`, `Blacklist Management Dialog`, `Opportunity Monitor Tests`, `Socket Connection Diagnostics`, `GradeOpcoesDialog`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 68 inferred relationships involving `ParametroRepository` (e.g. with `ColetarTaxasAluguelUseCase` and `MonitorBoxUseCase`) actually correct?**
  _`ParametroRepository` has 68 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `MainWindow` (e.g. with `_FiltroManutencao` and `ColetarTaxasAluguelUseCase`) actually correct?**
  _`MainWindow` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 60 inferred relationships involving `InstrumentoRepository` (e.g. with `ColetarTaxasAluguelUseCase` and `ExportarOperacaoUseCase`) actually correct?**
  _`InstrumentoRepository` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `OpenFastSocketAdapter` (e.g. with `FieldName` and `MarketDataSource`) actually correct?**
  _`OpenFastSocketAdapter` has 16 INFERRED edges - model-reasoned connections that need verification._