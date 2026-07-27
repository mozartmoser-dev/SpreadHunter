# Graph Report - .  (2026-07-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1791 nodes · 4696 edges · 120 communities (85 shown, 35 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 900 edges (avg confidence: 0.53)
- Token cost: 6,645 input · 1,255 output

## Graph Freshness
- Built from commit: `d736f02d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Options Pricing Calculator|Options Pricing Calculator]]
- [[_COMMUNITY_Opportunity Classification Logic|Opportunity Classification Logic]]
- [[_COMMUNITY_Asynchronous Tail Monitoring|Asynchronous Tail Monitoring]]
- [[_COMMUNITY_OpenFast Socket Adapter|OpenFast Socket Adapter]]
- [[_COMMUNITY_PETR4 Intraday Monitoring|PETR4 Intraday Monitoring]]
- [[_COMMUNITY_Market Data Source Interface|Market Data Source Interface]]
- [[_COMMUNITY_Database Migration Management|Database Migration Management]]
- [[_COMMUNITY_Collar Strategy Dialog|Collar Strategy Dialog]]
- [[_COMMUNITY_MPP Strategy Use Case|MPP Strategy Use Case]]
- [[_COMMUNITY_MPP Table Model|MPP Table Model]]
- [[_COMMUNITY_Trading Domain Enums|Trading Domain Enums]]
- [[_COMMUNITY_B3 Holiday Management|B3 Holiday Management]]
- [[_COMMUNITY_Instrument Data Repository|Instrument Data Repository]]
- [[_COMMUNITY_Dividend Data Provider|Dividend Data Provider]]
- [[_COMMUNITY_Main Application Window|Main Application Window]]
- [[_COMMUNITY_Market Data Provider|Market Data Provider]]
- [[_COMMUNITY_Box Strategy Dialog|Box Strategy Dialog]]
- [[_COMMUNITY_Collar Calendar Dialog|Collar Calendar Dialog]]
- [[_COMMUNITY_Monitor Table Model|Monitor Table Model]]
- [[_COMMUNITY_UI Settings Persistence|UI Settings Persistence]]
- [[_COMMUNITY_OpcoesNet API Client|OpcoesNet API Client]]
- [[_COMMUNITY_Operation Export Use Case|Operation Export Use Case]]
- [[_COMMUNITY_Stock Rental Rate Collection|Stock Rental Rate Collection]]
- [[_COMMUNITY_Earnings Calendar Provider|Earnings Calendar Provider]]
- [[_COMMUNITY_Market Data Mocking|Market Data Mocking]]
- [[_COMMUNITY_Collar Calendar Monitoring|Collar Calendar Monitoring]]
- [[_COMMUNITY_Operational Parameter Repository|Operational Parameter Repository]]
- [[_COMMUNITY_PNT Automation Interface|PNT Automation Interface]]
- [[_COMMUNITY_Earnings Calendar Repository|Earnings Calendar Repository]]
- [[_COMMUNITY_OpenFast Performance Testing|OpenFast Performance Testing]]
- [[_COMMUNITY_Export Configuration Dialog|Export Configuration Dialog]]
- [[_COMMUNITY_Trading Strategy Calculators|Trading Strategy Calculators]]
- [[_COMMUNITY_Opportunity Monitor Display|Opportunity Monitor Display]]
- [[_COMMUNITY_Sold Opportunity Model|Sold Opportunity Model]]
- [[_COMMUNITY_Table Cell Display Logic|Table Cell Display Logic]]
- [[_COMMUNITY_Market Data Adapter Tests|Market Data Adapter Tests]]
- [[_COMMUNITY_Covered Call Model|Covered Call Model]]
- [[_COMMUNITY_Trade History Dialog|Trade History Dialog]]
- [[_COMMUNITY_Opportunity Monitoring Service|Opportunity Monitoring Service]]
- [[_COMMUNITY_MPP and Rules Dialogs|MPP and Rules Dialogs]]
- [[_COMMUNITY_Collar Strategy Monitoring|Collar Strategy Monitoring]]
- [[_COMMUNITY_Payoff Visualization Dialog|Payoff Visualization Dialog]]
- [[_COMMUNITY_UI Styling and Delegates|UI Styling and Delegates]]
- [[_COMMUNITY_Telegram Notification Service|Telegram Notification Service]]
- [[_COMMUNITY_B3 Transaction Cost Calculator|B3 Transaction Cost Calculator]]
- [[_COMMUNITY_PNT Automation Utilities|PNT Automation Utilities]]
- [[_COMMUNITY_Collar Calendar Table Model|Collar Calendar Table Model]]
- [[_COMMUNITY_Engine Performance Dashboard|Engine Performance Dashboard]]
- [[_COMMUNITY_PNT Integration Service|PNT Integration Service]]
- [[_COMMUNITY_Collar Strategy Calculator|Collar Strategy Calculator]]
- [[_COMMUNITY_FastTrade Server Mock|FastTrade Server Mock]]
- [[_COMMUNITY_Audio Notification Service|Audio Notification Service]]
- [[_COMMUNITY_Parameters Configuration Widget|Parameters Configuration Widget]]
- [[_COMMUNITY_Box Strategy Monitoring|Box Strategy Monitoring]]
- [[_COMMUNITY_PNT Screen Management|PNT Screen Management]]
- [[_COMMUNITY_Strategy Explanation Dialog|Strategy Explanation Dialog]]
- [[_COMMUNITY_Application Entry Point|Application Entry Point]]
- [[_COMMUNITY_CDI Interest Calculator|CDI Interest Calculator]]
- [[_COMMUNITY_Covered Call Monitoring|Covered Call Monitoring]]
- [[_COMMUNITY_Sold Strategy Monitoring|Sold Strategy Monitoring]]
- [[_COMMUNITY_CVM Earnings Provider|CVM Earnings Provider]]
- [[_COMMUNITY_Blacklist Management Dialog|Blacklist Management Dialog]]
- [[_COMMUNITY_Whitelist Management Dialog|Whitelist Management Dialog]]
- [[_COMMUNITY_Opportunity Monitor Tests|Opportunity Monitor Tests]]
- [[_COMMUNITY_Box Strategy Table Model|Box Strategy Table Model]]
- [[_COMMUNITY_CDI Calculator Dialog|CDI Calculator Dialog]]
- [[_COMMUNITY_Box Strategy Calculator|Box Strategy Calculator]]
- [[_COMMUNITY_Scan Performance Diagnostics|Scan Performance Diagnostics]]
- [[_COMMUNITY_Socket Connection Diagnostics|Socket Connection Diagnostics]]
- [[_COMMUNITY_Project Dependencies|Project Dependencies]]
- [[_COMMUNITY_Graph Visualization Plugin|Graph Visualization Plugin]]
- [[_COMMUNITY_UI Automation Testing|UI Automation Testing]]
- [[_COMMUNITY_Application Branding Assets|Application Branding Assets]]
- [[_COMMUNITY_Build Runtime Hooks|Build Runtime Hooks]]
- [[_COMMUNITY_Market Data Configuration|Market Data Configuration]]
- [[_COMMUNITY_Spread Coefficient Calculator|Spread Coefficient Calculator]]
- [[_COMMUNITY_UI Preview Toolbar|UI Preview Toolbar]]
- [[_COMMUNITY_Liquidity Indicator Logic|Liquidity Indicator Logic]]
- [[_COMMUNITY_Main Application Package|Main Application Package]]
- [[_COMMUNITY_Tool UI Labels|Tool UI Labels]]
- [[_COMMUNITY_Large Tool Icons|Large Tool Icons]]
- [[_COMMUNITY_Standard Tool Icons|Standard Tool Icons]]
- [[_COMMUNITY_Basket Order Import|Basket Order Import]]
- [[_COMMUNITY_Directional Robot UI|Directional Robot UI]]
- [[_COMMUNITY_Order Type Labels|Order Type Labels]]
- [[_COMMUNITY_Order Type Headers|Order Type Headers]]
- [[_COMMUNITY_Performance Engine Icons|Performance Engine Icons]]

## God Nodes (most connected - your core abstractions)
1. `ParametroRepository` - 148 edges
2. `MainWindow` - 112 edges
3. `InstrumentoRepository` - 109 edges
4. `OpenFastSocketAdapter` - 84 edges
5. `InstrumentoOpcional` - 71 edges
6. `get_connection()` - 64 edges
7. `MonitorWorker` - 64 edges
8. `Palette` - 64 edges
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
- **PNT Automation Flow** — src_infrastructure_integrations_pnt, src_ui_desktop_boleta_dialog, docs_pnt_importacao [EXTRACTED 1.00]
- **Performance Optimization Wave** — src_infrastructure_providers_rtd_profit, src_infrastructure_persistence_database, tunning [EXTRACTED 1.00]
- **Toolbar UI Design Proposals** — temas_preview_toolbar, temas_preview_toolbar_vazado [EXTRACTED 1.00]
- **PNT Automation Assets** — src_infrastructure_integrations_pnt, src_infrastructure_integrations_pnt_images_debug_step4_down3, src_infrastructure_integrations_pnt_images_debug_step5_enter, src_infrastructure_integrations_pnt_images_ferramentas [INFERRED 0.90]

## Communities (120 total, 35 thin omitted)

### Community 0 - "Options Pricing Calculator"
Cohesion: 0.05
Nodes (16): CalculadoraColarCalendario, date, ResultadoColarCalendario, TipoColarCalendario, TestBlackScholes, TestBsTheta, TestCalcular, TestCalcularCdiPeriodo (+8 more)

### Community 1 - "Opportunity Classification Logic"
Cohesion: 0.06
Nodes (16): ClassificacaoOportunidade, CalculadoraBoxSbth, DadosMercado, ResultadoBOXSBTH, CandidatoPescaria, ElegibilidadePescaria, extrair_strike(), parse_vencimento() (+8 more)

### Community 2 - "Asynchronous Tail Monitoring"
Cohesion: 0.05
Nodes (7): CalculadoraCaudaAssincrona, Pós-processa um ResultadoColarCalendario viável e calcula o ratio     ótimo de C, ResultadoCaudaAssincrona, MonitorWorker, Tests for CalculadoraCaudaAssincrona — the cauda ratio optimizer., Cenário típico: CALL OTM, gap > 0, encontra N ótimo com BE >= 3σ., TestCaudaBasics

### Community 3 - "OpenFast Socket Adapter"
Cohesion: 0.06
Nodes (10): OpenFastSocketAdapter, Adapter tambem aceita # como separador., server(), TestOpenFastSocketAdapterCache, TestOpenFastSocketAdapterConecta, TestOpenFastSocketAdapterDirtyKeys, TestOpenFastSocketAdapterReconexao, TestOpenFastSocketAdapterRegistrar (+2 more)

### Community 4 - "PETR4 Intraday Monitoring"
Cohesion: 0.06
Nodes (13): Analise PETR4 com pivot points + suportes intraday via API + RTD., Monitor PETR4 — updates de 1 em 1 minuto, Monitor PETR4 — análise a cada 2 min com projecoes, Monitora PETR4 spot + OTM 38.36 por 5 min, Monitor contínuo do book PETR4 com análise de direção + volume., Monitor bounce PETR4 — analise a cada 30 segundos, Monitor PETR4 a cada 20s — divergencias + bounce, Script para ler PETR4 do Profit RTD e calcular Put Ratio Spread. (+5 more)

### Community 5 - "Market Data Source Interface"
Cohesion: 0.07
Nodes (8): Protocol, criar_data_source(), FieldName, MarketDataSource, Traduz FieldName → str Profit. RTDProfit permanece intacto., RTDProfitAdapter, TestDataSourceFactory, TestFieldNameEnum

### Community 6 - "Database Migration Management"
Cohesion: 0.06
Nodes (27): QTableWidgetItem, Testa migração de fonte_market_data 0/1 → profit/openfast., main(), ImportFlash: varre opcoes.net.br e atualiza o banco do SpreadHunter.  Captura o, _get_appdata_dir(), get_db_path(), _migrar_banco_legado(), _migrar_calendario_resultados() (+19 more)

### Community 7 - "Collar Strategy Dialog"
Cohesion: 0.07
Nodes (8): ColarDialog, ColarSortProxy, ColarTableModel, ler_whitelist_colar(), atualizar_resultados must restore header movable/blocked state after update., atualizar must wrap item replacement in beginResetModel/endResetModel., test_atualizar_resultados_header_freeze_restore(), test_colar_model_atualizar_chama_begin_end_reset()

### Community 8 - "MPP Strategy Use Case"
Cohesion: 0.09
Nodes (7): MPPUseCase, MreResultado, PernaImediata, date, Persiste spread history em batch — chamado no final do ciclo MPP., MercadoEstruturalProvider, date

### Community 9 - "MPP Table Model"
Cohesion: 0.07
Nodes (34): BoxScore, ResultadoBox, MppTableModel, _box_col_key(), _col_key(), _make_full_opp(), _mpp_model(), Tests that display formatting matches calculation in all 3 strategy dialogs.  If (+26 more)

### Community 10 - "Trading Domain Enums"
Cohesion: 0.19
Nodes (22): Enum, TipoExportacao, EstruturaOperacional, TipoEstrutura, TipoOpcao, ClassificacaoOp, Lado, PernaOperacao (+14 more)

### Community 11 - "B3 Holiday Management"
Cohesion: 0.08
Nodes (7): FeriadoB3Repository, FeriadosB3Provider, B3 fecha em 9 de Julho (Revolução Constitucionalista - feriado SP)., FeriadosDialog, FeriadosFetchWorker, FeriadosSortProxy, FeriadosTableModel

### Community 12 - "Instrument Data Repository"
Cohesion: 0.09
Nodes (19): Connection, Row, InstrumentoOpcional, init_db(), _seed_parametros_colar(), InstrumentoRepository, _parse_date(), date (+11 more)

### Community 13 - "Dividend Data Provider"
Cohesion: 0.08
Nodes (7): QThread, DividendosStatusInvestProvider, DividendosDialog, DividendosFetchWorker, DividendosTableModel, _AtualizarThread, TaxaAluguelDialog

### Community 15 - "Market Data Provider"
Cohesion: 0.10
Nodes (8): MercadoDataProvider, Registra apenas os ativos (underlyings) para obter preços de referência rápido., Registra todos os campos de um instrumento quando detectamos liquidez., Detecta novos books, registra Onda 2, background scan e salva prioridades., Retorna contagens internas para o Dashboard de Performance., Limpa as flags de cache e força o re-registro dos instrumentos no RTD., Open Fast nao usa CAB skip — suporta_cab_skip=False., TestMercadoProviderOpenFast

### Community 16 - "Box Strategy Dialog"
Cohesion: 0.12
Nodes (4): BoxDialog, Alerta se algum ativo nos resultados está em dia ex de dividendo., PipelineDialog, Diálogo de pipeline estilo Bloomberg (tabela horizontal com barras).

### Community 18 - "Monitor Table Model"
Cohesion: 0.16
Nodes (3): MonitorTableModel, _make_opp(), TestMonitorTableModel

### Community 19 - "UI Settings Persistence"
Cohesion: 0.17
Nodes (15): QSettings, tocar(), restaurar_ordem_colunas(), salvar_ordem_colunas(), _settings(), get_theme_qss(), Palette, sectionMoved via QTimer.singleShot(0) must not crash on rapid column reorder. (+7 more)

### Community 20 - "OpcoesNet API Client"
Cohesion: 0.12
Nodes (8): Session, OpcoesNetClient, Busca grade de opções (strike x vencimento) do opcoes.net.br.         tipo: 'CAL, Busca o mapping {ticker: 'A'/'E'} (MOD = modelo Americano/Europeu)         via A, Retorna lista de todos os ativos com opções disponíveis em opcoes.net.br., Busca todas as opções (CALL + PUT) de um ativo via API, incluindo         séries, Busca histórico de candles + volatilidade do ativo via API.         Request type, Retorna lista de candles {date, open, high, low, close, change, volume, vol_hist

### Community 21 - "Operation Export Use Case"
Cohesion: 0.10
Nodes (6): ExportarResultado, ExportarOperacaoUseCase, Oportunidade, OportunidadeRepository, oportunidade_repo(), TestExportarOperacaoUseCase

### Community 22 - "Stock Rental Rate Collection"
Cohesion: 0.18
Nodes (7): ColetarTaxasAluguelUseCase, TaxaAluguel, InvestSiteClient, TaxaAluguelRepository, TestColetarTaxasAluguelUseCase, TestInvestSiteClient, TestTaxaAluguelRepository

### Community 23 - "Earnings Calendar Provider"
Cohesion: 0.11
Nodes (4): CalendarioResultadosWebwalletProvider, CalendarioFetchWorker, CalendarioResultadosDialog, CalendarioTableModel

### Community 24 - "Market Data Mocking"
Cohesion: 0.13
Nodes (7): MockMarketDataProvider, DadosRTDInstrumento, TestDadosRTDInstrumento, TestMockMarketDataProvider, TestMonitorWorker, TestRTDConfig, TestRTDProfitWithoutCOM

### Community 25 - "Collar Calendar Monitoring"
Cohesion: 0.13
Nodes (7): Collar Calendário Cauda Assíncrona Study, MonitorColaresCalendarioUseCase, PipelineStage, PipelineTracker, Coleta dados do pipeline de filtros sem afetar a execução.      Uso:         tra, adapter(), RTDProfitAdapter com RTDProfit mockado.

### Community 26 - "Operational Parameter Repository"
Cohesion: 0.17
Nodes (8): ParametroOperacional, ParametroRepository, ler_blacklist(), salvar_blacklist(), NoWheelSpinBox, ler_whitelist(), salvar_whitelist(), parametro_repo()

### Community 27 - "PNT Automation Interface"
Cohesion: 0.11
Nodes (23): PNT Import Documentation, _achar_combobox(), _achar_janela_pnt(), _debug_screenshot(), _diagnostic_list_windows(), executar_automacao_pnt(), PNT UI Debug Screenshot, PNT UI Debug Step 4 (+15 more)

### Community 28 - "Earnings Calendar Repository"
Cohesion: 0.13
Nodes (4): get_connection(), CalendarioResultadosRepository, DividendoRepository, Retorna dicionário {(ativo, cod_put): InstrumentoOpcional}.         Chave compo

### Community 29 - "OpenFast Performance Testing"
Cohesion: 0.12
Nodes (11): LoadSimulator, socket, Teste de performance da _thread_leitora do OpenFastSocketAdapter.  Simula o serv, Espera a thread leitora processar N atualizações no cache., Mede quão rápido a thread leitora processa dados em lote., Mede o custo do parse + batch mutex (nova abordagem)., Simula contenção: thread leitora + main thread lendo cache., Servidor que simula o fasttrader enviando push para N instrumentos. (+3 more)

### Community 30 - "Export Configuration Dialog"
Cohesion: 0.17
Nodes (7): QDoubleSpinBox, QLabel, ExportDialog, QFrame, QWidget, Aciona a integração visual com o PNT com feedback de progresso., Nível 3: Alerta se o ativo estiver em dia ex de dividendo hoje.

### Community 31 - "Trading Strategy Calculators"
Cohesion: 0.17
Nodes (12): ndarray, ResultadoVetorizado, atualizar_calendario(), dc_to_du(), dc_to_du_aproximado(), dc_to_du_exato(), dc_to_du_vetorizado(), eh_feriado() (+4 more)

### Community 32 - "Opportunity Monitor Display"
Cohesion: 0.12
Nodes (4): OportunidadeMonitor, monitor_uc(), test_mensagem_telegram_pct_ganho_box_formatado_corretamente(), test_mensagem_telegram_pct_ganho_formatado_corretamente()

### Community 34 - "Table Cell Display Logic"
Cohesion: 0.14
Nodes (20): _monitor_col_key(), _monitor_opp(), MonitorTableModel cell display for BOX strategy., ganho_display must use percent_sbth for SBTH classification., ganho_display must use max(ganho_box, ganho_sbth) for BOX+SBTH., ganho_display must use sbth for 2SBTH regardless of box value., ganho_display must show '-' when both percentages are zero., tipo_opcao mapping: A→AMER, E→EUR, P→PUT. (+12 more)

### Community 38 - "Opportunity Monitoring Service"
Cohesion: 0.21
Nodes (4): MonitorOportunidadesUseCase, CalculadoraVetorizada, monitor_uc(), TestMonitorOportunidadesUseCase

### Community 39 - "MPP and Rules Dialogs"
Cohesion: 0.16
Nodes (3): QTableWidget, MppDialog, RegrasDialog

### Community 40 - "Collar Strategy Monitoring"
Cohesion: 0.24
Nodes (5): MonitorColaresUseCase, DadosPata, ResultadoColar, RiscoLeilao, TipoColar

### Community 41 - "Payoff Visualization Dialog"
Cohesion: 0.23
Nodes (6): QDialog, copiar_figura_clipboard(), Renderiza matplotlib Figure para PNG e cola como imagem no clipboard., Salva matplotlib Figure como PNG via diálogo., salvar_figura_arquivo(), plot_historico()

### Community 42 - "UI Styling and Delegates"
Cohesion: 0.14
Nodes (4): QIcon, QStyledItemDelegate, BadgeDelegate, _make_led_icon()

### Community 43 - "Telegram Notification Service"
Cohesion: 0.19
Nodes (4): TelegramNotifier, Fetch token, chat_id and enable flag from the parameters table.         Returns, Facade that reads telegram configuration from the DB and sends messages.     It, TelegramService

### Community 44 - "B3 Transaction Cost Calculator"
Cohesion: 0.17
Nodes (5): CalculadoraCustosB3, Taxa total para opções (emol + liq + reg + iss)., Taxa total para ações (emol + liq + iss — sem registro)., Custo B3 para opções: taxa_total × prêmio médio × pernas × (2 se ida_e_volta)., Custo B3 para ações: taxa_total_stock × preço × ações × (2 se ida_e_volta).

### Community 45 - "PNT Automation Utilities"
Cohesion: 0.16
Nodes (8): _achar_janela_pnt_por_processo(), _focar_janela_pnt(), Localiza HWND do PNT pelo nome do processo PnT.Inteface.exe., Localiza e ativa a janela do PNT: processo > título., Testes unitários da automação PNT com mocks (mercado fechado)., TestBuscaPorProcesso, TestRoboComAcento, TestSwitchToThisWindow

### Community 46 - "Collar Calendar Table Model"
Cohesion: 0.22
Nodes (3): QAbstractTableModel, ColarCalSortProxy, ColarCalTableModel

### Community 47 - "Engine Performance Dashboard"
Cohesion: 0.23
Nodes (6): QFrame, BasketGerada, EngineStatsDTO, ImportarResultado, EngineDashboard, StatCard

### Community 48 - "PNT Integration Service"
Cohesion: 0.19
Nodes (6): PNTIntegration, Integração com PlugNTrade via automação de interface (GUI) usando Clipboard., Busca parâmetros operacionais no banco de dados., Limpa o campo atual e digita o valor formatado (ponto para vírgula)., Monta dados no formato de importação direcional do PlugNTrade., Envia a oportunidade usando o fluxo correto de importação do PNT.

### Community 51 - "FastTrade Server Mock"
Cohesion: 0.19
Nodes (5): MockFastTradeServer, socket, Simula chegada de SQT., Servidor TCP fake que emula Open Fast. Porta 5557 para não conflitar., server()

### Community 52 - "Audio Notification Service"
Cohesion: 0.45
Nodes (10): Path, _carregar_params(), _gerar_wav_volume(), testar(), testar_coberta(), testar_vendidas(), tocar_coberta(), _tocar_premio() (+2 more)

### Community 53 - "Parameters Configuration Widget"
Cohesion: 0.31
Nodes (3): QComboBox, QWidget, ParametrosWidget

### Community 55 - "PNT Screen Management"
Cohesion: 0.25
Nodes (5): PNTScreenManager, Gerenciador de telas do PNT via reconhecimento de imagem, Encontra e foca a janela do PNT usando Win32 API (ou fallback pyautogui)., Abre a tela MultiLeg manualmente (usuário deve fazer isso), Abre a tela Spread manualmente (usuário deve fazer isso)

### Community 56 - "Strategy Explanation Dialog"
Cohesion: 0.27
Nodes (4): QTextEdit, CalculadoraDialog, copiar_texto_formatado(), Copia conteúdo do QTextEdit como HTML + plain text para o clipboard.

### Community 57 - "Application Entry Point"
Cohesion: 0.33
Nodes (5): _clear_pycache(), _FiltroManutencao, run_app(), carregar_do_banco(), bootstrap()

### Community 58 - "CDI Interest Calculator"
Cohesion: 0.36
Nodes (5): _br(), CalculadoraCDI, main(), Calculadora CDI ============================= Calcula o valor a investir hoje pa, Formata número no padrão BR: 1234.5 -> '1.234,50'.

### Community 65 - "Box Strategy Table Model"
Cohesion: 0.13
Nodes (6): QSortFilterProxyModel, BoxSortProxy, BoxTableModel, CalendarioSortProxy, DividendosSortProxy, Proxy que ordena datas ISO e numeros corretamente.

### Community 74 - "Application Branding Assets"
Cohesion: 0.67
Nodes (3): Spreadhunter Disclaimer, Spreadhunter Opening Theme, Spreadhunter Initializing Theme

## Knowledge Gaps
- **21 isolated node(s):** `@opencode-ai/plugin`, `spreadhunter`, `ImportarResultado`, `BasketGerada`, `PNT Import Documentation` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **35 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ParametroRepository` connect `Operational Parameter Repository` to `Asynchronous Tail Monitoring`, `Database Migration Management`, `Collar Strategy Dialog`, `MPP Strategy Use Case`, `MPP Table Model`, `Trading Domain Enums`, `B3 Holiday Management`, `Instrument Data Repository`, `Main Application Window`, `Market Data Provider`, `Collar Calendar Dialog`, `Monitor Table Model`, `UI Settings Persistence`, `Operation Export Use Case`, `Stock Rental Rate Collection`, `Market Data Mocking`, `Collar Calendar Monitoring`, `PNT Automation Interface`, `Trading Strategy Calculators`, `Opportunity Monitor Display`, `Covered Call Model`, `Opportunity Monitoring Service`, `MPP and Rules Dialogs`, `Collar Strategy Monitoring`, `Payoff Visualization Dialog`, `UI Styling and Delegates`, `Telegram Notification Service`, `Collar Calendar Table Model`, `PNT Integration Service`, `Audio Notification Service`, `Parameters Configuration Widget`, `Box Strategy Monitoring`, `PNT Screen Management`, `Application Entry Point`, `Covered Call Monitoring`, `Sold Strategy Monitoring`, `Blacklist Management Dialog`, `Whitelist Management Dialog`, `Opportunity Monitor Tests`, `CDI Calculator Dialog`?**
  _High betweenness centrality (0.242) - this node is a cross-community bridge._
- **Why does `InstrumentoRepository` connect `Instrument Data Repository` to `Opportunity Classification Logic`, `Asynchronous Tail Monitoring`, `Collar Strategy Dialog`, `Trading Domain Enums`, `Dividend Data Provider`, `Main Application Window`, `Market Data Provider`, `Collar Calendar Dialog`, `Monitor Table Model`, `UI Settings Persistence`, `Operation Export Use Case`, `Stock Rental Rate Collection`, `Market Data Mocking`, `Collar Calendar Monitoring`, `Operational Parameter Repository`, `Earnings Calendar Repository`, `Trading Strategy Calculators`, `Covered Call Model`, `Opportunity Monitoring Service`, `Collar Strategy Monitoring`, `Telegram Notification Service`, `Collar Calendar Table Model`, `Box Strategy Monitoring`, `Covered Call Monitoring`, `Sold Strategy Monitoring`, `Opportunity Monitor Tests`, `Box Strategy Table Model`, `CDI Calculator Dialog`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `FieldName` connect `Market Data Source Interface` to `OpenFast Socket Adapter`, `Market Data Adapter Tests`, `Collar Strategy Monitoring`, `MPP Table Model`, `MPP Strategy Use Case`, `Trading Domain Enums`, `Instrument Data Repository`, `Market Data Provider`, `Box Strategy Monitoring`, `Collar Calendar Monitoring`, `OpenFast Performance Testing`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Are the 65 inferred relationships involving `ParametroRepository` (e.g. with `ColetarTaxasAluguelUseCase` and `MonitorBoxUseCase`) actually correct?**
  _`ParametroRepository` has 65 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `MainWindow` (e.g. with `_FiltroManutencao` and `ColetarTaxasAluguelUseCase`) actually correct?**
  _`MainWindow` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 58 inferred relationships involving `InstrumentoRepository` (e.g. with `ColetarTaxasAluguelUseCase` and `ExportarOperacaoUseCase`) actually correct?**
  _`InstrumentoRepository` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `OpenFastSocketAdapter` (e.g. with `FieldName` and `MarketDataSource`) actually correct?**
  _`OpenFastSocketAdapter` has 16 INFERRED edges - model-reasoned connections that need verification._