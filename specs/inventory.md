# Spreadhunter — Inventário Arquitetural

> Windows-only. Python 3.13 / PySide6 6.11.1 / SQLite (WAL). 573 testes. Sem CI.

---

## Camada 0 — Kernel & Contratos

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `InstrumentoOpcional` | 0 | `dataclasses`, `datetime`, `enum` | `src/domain/entities/instrumento_opcional.py` | Não | Sim | [ ] Pendente |
| `TipoOpcao` (enum) | 0 | `enum` | `src/domain/entities/instrumento_opcional.py` | Não | Sim | [ ] Pendente |
| `Oportunidade` | 0 | `dataclasses`, `enum` | `src/domain/entities/oportunidade.py` | Não | Sim | [ ] Pendente |
| `ClassificacaoOp` (enum) | 0 | `enum` | `src/domain/entities/oportunidade.py` | Não | Sim | [ ] Pendente |
| `EstruturaOperacional` | 0 | `dataclasses`, `enum` | `src/domain/entities/estrutura_operacional.py` | Não | Sim | [ ] Pendente |
| `TipoEstrutura` (enum) | 0 | `enum` | `src/domain/entities/estrutura_operacional.py` | Não | Sim | [ ] Pendente |
| `PernaOperacao` | 0 | `dataclasses`, `enum` | `src/domain/entities/perna_operacao.py` | Não | Sim | [ ] Pendente |
| `Lado` (enum) | 0 | `enum` | `src/domain/entities/perna_operacao.py` | Não | Sim | [ ] Pendente |
| `ParametroOperacional` | 0 | `dataclasses` | `src/domain/entities/parametro_operacional.py` | Não | Parcial | [ ] Pendente |
| `TaxaAluguel` | 0 | `dataclasses`, `datetime` | `src/domain/entities/taxa_aluguel.py` | Não | Sim | [ ] Pendente |
| `WorkspaceSnapshot` | 0 | `dataclasses`, `datetime`, `json` | `src/domain/entities/workspace_snapshot.py` | Não | Sim | [ ] Pendente |
| `OportunidadeMonitor` (DTO) | 0 | `dataclasses`, `datetime`, `enum`, `zoneinfo` | `src/application/dtos/dtos.py` | Não | Sim | [ ] Pendente |
| `BasketGerada` (DTO) | 0 | `dataclasses` | `src/application/dtos/dtos.py` | Não | Não | [ ] Pendente |
| `ExportarResultado` (DTO) | 0 | `dataclasses` | `src/application/dtos/dtos.py` | Não | Parcial | [ ] Pendente |
| `EngineStatsDTO` | 0 | `dataclasses` | `src/application/dtos/dtos.py` | Não | Não | [ ] Pendente |
| `ImportarResultado` (DTO) | 0 | `dataclasses` | `src/application/dtos/dtos.py` | Não | Não | [ ] Pendente |
| `TipoExportacao` (enum) | 0 | `enum` | `src/application/dtos/dtos.py` | Não | Parcial | [ ] Pendente |
| `OportunidadeVendaCoberta` (DTO) | 0 | `dataclasses`, `datetime`, `zoneinfo` | `src/application/dtos/dtos_venda_coberta.py` | Não | Sim | [ ] Pendente |
| `OportunidadeVendida` (DTO) | 0 | `dataclasses`, `datetime`, `zoneinfo` | `src/application/dtos/dtos_vendida.py` | Não | Sim | [ ] Pendente |
| `ClassificacaoOportunidade` (regras) | 0 | `entities.oportunidade`, `calculadora_box_sbth` | `src/domain/rules/classificacao_oportunidade.py` | Não | Sim | [ ] Pendente |
| `CalculadoraCustosB3` | 0 | `numpy` (lazy) | `src/domain/services/calculadora_custos_b3.py` | Não | Sim | [ ] Pendente |
| `CalendarioB3` | 0 | `datetime`, `numpy`, `FeriadoB3Repository` (lazy) | `src/domain/services/calendario_b3.py` | Não (global mutável) | Parcial | [ ] Pendente |
| `PipelineTracker` | 0 | `logging`, `time`, `dataclasses` | `src/domain/services/pipeline_tracker.py` | Não | Não | [ ] Pendente |
| `FieldName` (enum) | 0 | `enum` | `src/domain/services/market_data_source.py` | Não | Sim | [ ] Pendente |
| `MarketDataSource` (Protocol) | 0 | `typing.Protocol`, `runtime_checkable` | `src/domain/services/market_data_source.py` | Não | Sim | [ ] Pendente |
| `criar_data_source` (factory) | 0 | `typing` | `src/domain/services/market_data_source.py` | Não | Sim | [ ] Pendente |
| `Database` (schema + pool) | 0 | `hashlib`, `json`, `sqlite3`, `threading`, `pathlib` | `src/infrastructure/persistence/database.py` | Sim (`threading.local`) | Sim | [ ] Pendente |
| `Bootstrap` | 0 | `database`, `repositories`, `calendario_b3`, `workspace_service` | `src/infrastructure/persistence/bootstrap.py` | Não | Não | [ ] Pendente |
| `parametros_default.json` | 0 | — (arquivo estático) | `config/parametros_default.json` | Não | Não | [ ] Pendente |
| `spreadhunter_prioridade.json` | 0 | — (arquivo estático) | `config/spreadhunter_prioridade.json` | Não | Não | [ ] Pendente |

---

## Camada 1 — Infraestrutura & Streaming

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `RTDProfit` (COM client) | 1 | `rtd_config`, `threading`, `win32com.client` | `src/infrastructure/providers/rtd_profit.py` | Sim (`threading.Lock` + COM) | Parcial | [ ] Pendente |
| `RTDProfitAdapter` | 1 | `rtd_profit`, `market_data_source` | `src/infrastructure/providers/rtd_profit_adapter.py` | Não (delega) | Sim | [ ] Pendente |
| `rtd_config` (constantes + DTO) | 1 | `dataclasses` | `src/infrastructure/providers/rtd_config.py` | Não | Parcial | [ ] Pendente |
| `OpenFastSocketAdapter` | 1 | `socket`, `threading`, `market_data_source` | `src/infrastructure/providers/openfast_socket_adapter.py` | Sim (`threading.Lock` + daemon reader thread) | Sim | [ ] Pendente |
| `MercadoDataProvider` | 1 | `rtd_config`, `repositories`, `instrumento_opcional`, `market_data_source`, `PySide6.QMutex` | `src/infrastructure/providers/mercado_data_provider.py` | Sim (`QMutex`, Onda 1/2) | Parcial | [ ] Pendente |
| `MockMarketDataProvider` | 1 | `dtos`, `market_data_source` | `src/infrastructure/providers/mock_market_data.py` | Não | Parcial | [ ] Pendente |
| `MercadoEstruturalProvider` | 1 | `requests`, `urllib`, `math` | `src/infrastructure/providers/mercado_estrutural_provider.py` | Não | Não | [ ] Pendente |
| `FeriadosB3Provider` | 1 | `requests` | `src/infrastructure/providers/feriados_b3_provider.py` | Não | Não | [ ] Pendente |
| `CalendarioResultadosCVM` | 1 | `requests`, `zipfile`, `csv` | `src/infrastructure/providers/calendario_resultados_cvm.py` | Não | Não | [ ] Pendente |
| `CalendarioResultadosWebWallet` | 1 | `requests`, `bs4` | `src/infrastructure/providers/calendario_resultados_webwallet.py` | Não | Não | [ ] Pendente |
| `DividendosStatusInvest` | 1 | `requests`, `bs4`, `calendario_b3` | `src/infrastructure/providers/dividendos_statusinvest.py` | Não | Não | [ ] Pendente |
| `InstrumentoRepository` | 1 | `sqlite3`, `database`, `instrumento_opcional` | `src/infrastructure/persistence/repositories/repositories.py` | Sim (`threading.Lock` de classe) | Sim | [ ] Pendente |
| `ParametroRepository` | 1 | `sqlite3`, `database`, `parametro_operacional` | `src/infrastructure/persistence/repositories/repositories.py` | Sim (`threading.Lock` per-chave + `_dict_lock`) | Sim | [ ] Pendente |
| `OportunidadeRepository` | 1 | `sqlite3`, `database`, `oportunidade` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Sim | [ ] Pendente |
| `EstruturaRepository` | 1 | `sqlite3`, `database`, `estrutura_operacional` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Sim | [ ] Pendente |
| `PernaRepository` | 1 | `sqlite3`, `database`, `perna_operacao` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Sim | [ ] Pendente |
| `DividendoRepository` | 1 | `sqlite3`, `database` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Não | [ ] Pendente |
| `FeriadoB3Repository` | 1 | `sqlite3`, `database` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Não | [ ] Pendente |
| `TaxaAluguelRepository` | 1 | `sqlite3`, `database`, `taxa_aluguel` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Sim | [ ] Pendente |
| `CalendarioResultadosRepository` | 1 | `sqlite3`, `database` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Não | [ ] Pendente |
| `HistoricoSimulacoesRepository` | 1 | `sqlite3`, `database` | `src/infrastructure/persistence/repositories/repositories.py` | Não | Não | [ ] Pendente |
| `WorkspaceSnapshotRepository` | 1 | `workspace_snapshot`, `database` | `src/infrastructure/persistence/repositories/workspace_repository.py` | Não | Sim | [ ] Pendente |
| `OpcoesNetClient` | 1 | `requests`, `bs4`, `dotenv`, `re` | `src/infrastructure/integrations/opcoesnet_client.py` | Não (session HTTP) | Não | [ ] Pendente |
| `InvestSiteClient` | 1 | `requests`, `bs4`, `re` | `src/infrastructure/integrations/investsite_client.py` | Não | Sim | [ ] Pendente |
| `IbovCompositionClient` | 1 | `json`, `os` | `src/infrastructure/integrations/ibov_composition_client.py` | Não | Não | [ ] Pendente |
| `PNTIntegration` (GUI automation) | 1 | `ctypes`, `pyautogui`, `pyperclip`, `win32gui`, `pygetwindow`, `psutil` | `src/infrastructure/integrations/pnt.py` | Não (sequencial) | Sim | [ ] Pendente |
| `ExcelImporter` (utils) | 1 | `re`, `math`, `datetime` | `src/infrastructure/importers/excel_importer.py` | Não | Parcial | [ ] Pendente |
| `TelegramNotifier` | 1 | `requests` | `src/infrastructure/notifications/telegram_notifier.py` | Não | Sim (indireto) | [ ] Pendente |
| `TelegramService` | 1 | `telegram_notifier`, `repositories` | `src/infrastructure/notifications/telegram_service.py` | Não (throttle) | Sim | [ ] Pendente |
| `SomService` (alertas) | 1 | `PySide6.QtMultimedia`, `struct`, `wave`, `winsound`, `repositories` | `src/infrastructure/services/som_service.py` | Não (`QEventLoop` bloqueante) | Não | [ ] Pendente |

---

## Camada 2 — Estratégias & Regras Financeiras

### Calculadoras Base

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `CalculadoraBox` (4 pernas) | 2 | `calendario_b3`, `calculadora_custos_b3` | `src/domain/services/calculadora_box.py` | Não | Parcial | [ ] Pendente |
| `CalculadoraBoxSbth` (short + hedge) | 2 | `calendario_b3`, `calculadora_custos_b3` | `src/domain/services/calculadora_box_sbth.py` | Não | Parcial | [ ] Pendente |
| `CalculadoraColar` (protetivo) | 2 | `numpy`, `scipy.stats.norm`, `scipy.optimize.brentq`, `calendario_b3`, `calculadora_custos_b3` | `src/domain/services/calculadora_colar.py` | Não | Parcial | [ ] Pendente |
| `CalculadoraColarCalendario` | 2 | `numpy`, `scipy.stats.norm`, `scipy.optimize.brentq`, `calendario_b3`, `calculadora_custos_b3` | `src/domain/services/calculadora_colar_calendario.py` | Não | Sim | [ ] Pendente |
| `CalculadoraPutRatio` | 2 | `math`, `scipy.stats.norm`, `calendario_b3`, `calculadora_custos_b3` | `src/domain/services/calculadora_put_ratio.py` | Não | Sim | [ ] Pendente |
| `MarketAnalyzer` (macro) | 2 | `logging` | `src/domain/services/analise_mercado.py` | Não | Não | [ ] Pendente |
| `ElegibilidadePescaria` | 2 | `dataclasses` | `src/domain/services/elegibilidade_pescaria.py` | Não | Parcial | [ ] Pendente |
| `MontadoraBoxItm` | 2 | `entities.estrutura_operacional`, `entities.perna_operacao` | `src/domain/services/montadora_box_itm.py` | Não | Parcial | [ ] Pendente |

### Otimização

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `CalculadoraCaudaAssincrona` | 2 | `math`, `uuid`, `calendario_b3`, `calculadora_colar_calendario` | `src/domain/services/calculadora_cauda_assincrona.py` | Não | Sim | [ ] Pendente |
| `CalculadoraProtecaoCauda` | 2 | `json`, `math`, `scipy.stats.norm`, `calculadora_cauda_assincrona` | `src/domain/services/calculadora_protecao_cauda.py` | Não | Sim (55 testes) | [ ] Pendente |
| `CalculadoraVetorizada` | 2 | `numpy`, `calendario_b3`, `calculadora_custos_b3` | `src/domain/services/calculadora_vetorizada.py` | Não | Não | [ ] Pendente |

### Use Cases (orquestração)

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `MonitorOportunidadesUseCase` | 2 | `numpy`, `calculadora_box_sbth`, `calculadora_vetorizada`, `pipeline_tracker`, `repositories`, `telegram_service` | `src/application/use_cases/monitor_oportunidades.py` | Não (síncrono) | Sim | [ ] Pendente |
| `MonitorColaresUseCase` | 2 | `calculadora_colar`, `market_data_source`, `pipeline_tracker`, `repositories` | `src/application/use_cases/monitor_colares.py` | Não | Não | [ ] Pendente |
| `MonitorColaresCalendarioUseCase` | 2 | `calculadora_colar_calendario`, `opcoesnet_client`, `market_data_source`, `pipeline_tracker`, `repositories` | `src/application/use_cases/monitor_colares_calendario.py` | Não | Não | [ ] Pendente |
| `MonitorBoxUseCase` (4P) | 2 | `calculadora_box`, `market_data_source`, `pipeline_tracker`, `repositories` | `src/application/use_cases/monitor_box.py` | Não | Não | [ ] Pendente |
| `MonitorPutRatioUseCase` | 2 | `calculadora_put_ratio`, `opcoesnet_client`, `market_data_source`, `pipeline_tracker`, `repositories` | `src/application/use_cases/monitor_put_ratio.py` | Não | Não | [ ] Pendente |
| `MonitorVendidasUseCase` | 2 | `calculadora_custos_b3`, `calendario_b3`, `pipeline_tracker`, `repositories` | `src/application/use_cases/monitor_vendidas.py` | Não | Não | [ ] Pendente |
| `MonitorVendaCobertaUseCase` | 2 | `calculadora_custos_b3`, `calendario_b3`, `pipeline_tracker`, `repositories` | `src/application/use_cases/monitor_venda_coberta.py` | Não | Não | [ ] Pendente |
| `MPPUseCase` (priorização) | 2 | `calendario_b3`, `market_data_source`, `database`, `repositories` | `src/application/use_cases/mpp_use_case.py` | Não (cache por `update_counter`) | Sim | [ ] Pendente |
| `ColetarTaxasAluguelUseCase` | 2 | `investsite_client`, `repositories`, `taxa_aluguel` | `src/application/use_cases/coletar_taxas_aluguel.py` | Não | Parcial | [ ] Pendente |
| `ExportarOperacaoUseCase` | 2 | `montadora_box_itm`, `excel_importer`, `entities.*`, `repositories` | `src/application/use_cases/exportar_operacao.py` | Não | Parcial | [ ] Pendente |

### Serviços de Aplicação

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `SimuladorService` | 2 | `json`, `subprocess`, `sys`, `webbrowser` | `src/application/services/simulador_service.py` | Não (`subprocess`) | Não | [ ] Pendente |
| `WorkspaceService` | 2 | `PySide6.QSettings`, `workspace_snapshot`, `repositories` | `src/application/services/workspace_service.py` | Não | Sim | [ ] Pendente |

---

## Camada 3 — Aplicação & UI

| Nome do Módulo | Camada | Dependências Diretas | Arquivos Físicos | Concorrência | Testes | Status |
|---|---|---|---|---|---|---|
| `main.py` (entry point) | 3 | `PySide6`, `bootstrap`, `main_window` | `main.py` | Não | Não | [ ] Pendente |
| `MainWindow` (janela principal) | 3 | `PySide6`, `database`, `exportar_operacao`, `theme`, `table_models`, `monitor_worker`, ~15 dialogs, `repositories`, `column_utils`, `mercado_topbar` | `src/ui/desktop/main_window.py` | Sim (`QThread`, `QTimer`, `Signals`) | Parcial | [ ] Pendente |
| `MonitorWorker` (thread de fundo) | 3 | `PySide6`, todos os 7+ use cases, `pipeline_tracker`, `calculadora_cauda_assincrona`, `calculadora_protecao_cauda`, `calculadora_colar_calendario`, `calculadora_colar`, `repositories`, `market_data_source`, `mercado_data_provider` | `src/ui/desktop/monitor_worker.py` | Sim (`QThread`, `QMutex`, `QWaitCondition`, `CoInitializeEx`) | Parcial | [ ] Pendente |
| `MonitorTableModel` | 3 | `PySide6.QAbstractTableModel`, `dtos.OportunidadeMonitor`, `flag_icons`, `theme` | `src/ui/desktop/monitor_table_model.py` | Não | Sim | [ ] Pendente |
| `VendidasTableModel` | 3 | `PySide6.QAbstractTableModel`, `dtos_vendida`, `flag_icons`, `theme` | `src/ui/desktop/vendidas_table_model.py` | Não | Sim | [ ] Pendente |
| `VendaCobertaTableModel` | 3 | `PySide6.QAbstractTableModel`, `dtos_venda_coberta`, `flag_icons`, `theme` | `src/ui/desktop/venda_coberta_table_model.py` | Não | Sim | [ ] Pendente |
| `MppTableModel` | 3 | `PySide6.QAbstractTableModel` | `src/ui/desktop/mpp_table_model.py` | Não | Sim | [ ] Pendente |
| `ColarDialog` | 3 | `PySide6`, `opcoesnet_client`, `column_utils`, `copy_utils`, `theme`, `constants`, `calendario_b3` | `src/ui/desktop/colar_dialog.py` | Sim (`QTimer`) | Sim | [ ] Pendente |
| `ColarCalendarioDialog` | 3 | `PySide6`, `calendario_b3`, `opcoesnet_client`, `repositories`, `column_utils`, `copy_utils`, `theme`, `constants` | `src/ui/desktop/colar_calendario_dialog.py` | Sim (`QTimer`) | Sim | [ ] Pendente |
| `BoxDialog` | 3 | `PySide6`, `column_utils`, `flag_icons`, `theme` | `src/ui/desktop/box_dialog.py` | Sim (`QTimer`) | Sim | [ ] Pendente |
| `MppDialog` | 3 | `PySide6`, `column_utils`, `mpp_table_model`, `theme`, `repositories` | `src/ui/desktop/mpp_dialog.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `PutRatioDialog` | 3 | `scipy.stats.norm`, `PySide6`, `column_utils`, `constants`, `theme` | `src/ui/desktop/put_ratio_dialog.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `BoletaDialog` (envio PNT) | 3 | `PySide6`, `database`, `repositories`, `theme`, `pnt_utils`, `pnt` | `src/ui/desktop/boleta_dialog.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `CalculadorasDialog` | 3 | `PySide6`, `calculadora_colar`, `calendario_b3`, `repositories`, `theme` | `src/ui/desktop/calculadoras_dialog.py` | Não | Não | [ ] Pendente |
| `ExportDialog` | 3 | `PySide6`, `dtos`, `exportar_operacao`, `theme` | `src/ui/desktop/export_dialog.py` | Não | Sim | [ ] Pendente |
| `GradeOpcoesDialog` | 3 | `PySide6`, `TipoOpcao`, `repositories`, `flag_icons`, `theme` | `src/ui/desktop/grade_opcoes_dialog.py` | Sim (`_ImportThread` QThread) | Não | [ ] Pendente |
| `HistoricoDialog` | 3 | `json`, `datetime`, `PySide6`, `copy_utils`, `theme` | `src/ui/desktop/historico_dialog.py` | Não | Não | [ ] Pendente |
| `HistoricoSimulacoesDialog` | 3 | `PySide6`, `database`, `repositories`, `column_utils`, `theme` | `src/ui/desktop/historico_simulacoes_dialog.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `PipelineDialog` | 3 | `PySide6`, `pipeline_tracker` | `src/ui/desktop/pipeline_dialog.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `WorkspaceDialog` | 3 | `PySide6`, `workspace_service`, `workspace_snapshot`, `column_utils` | `src/ui/desktop/workspace_dialog.py` | Sim (`Signal`) | Sim | [ ] Pendente |
| `ParametrosWidget` | 3 | `json`, `PySide6`, `repositories`, `parametro_operacional`, `theme` | `src/ui/desktop/parametros_widget.py` | Não | Não | [ ] Pendente |
| `RegrasDialog` | 3 | `PySide6`, `theme`, `parametro_operacional`, imports dinâmicos de `FILTROS_*` | `src/ui/desktop/regras_dialog.py` | Não | Não | [ ] Pendente |
| `column_utils` | 3 | `PySide6.QSettings`, `hashlib` | `src/ui/desktop/column_utils.py` | Não | Sim | [ ] Pendente |
| `constants` | 3 | — | `src/ui/desktop/constants.py` | Não | Não | [ ] Pendente |
| `copy_utils` | 3 | `PySide6` (QClipboard, QFileDialog), `io` | `src/ui/desktop/copy_utils.py` | Não | Sim | [ ] Pendente |
| `theme` (Dark + Palette) | 3 | — | `src/ui/desktop/theme.py` | Não | Não | [ ] Pendente |
| `BadgeDelegate` | 3 | `PySide6.QStyledItemDelegate`, `QPainter` | `src/ui/desktop/badge_delegate.py` | Não | Não | [ ] Pendente |
| `flag_icons` | 3 | `math`, `PySide6.QPainter`, `QIcon`, `QPixmap` | `src/ui/desktop/flag_icons.py` | Não | Não | [ ] Pendente |
| `pnt_utils` | 3 | `PySide6.QApplication` | `src/ui/desktop/pnt_utils.py` | Não | Não | [ ] Pendente |
| `MercadoTopBarWidget` | 3 | `datetime`, `PySide6`, `market_data_source` | `src/ui/desktop/mercado_topbar.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `EngineDashboard` | 3 | `os`, `psutil`, `PySide6`, `theme`, `dtos.EngineStatsDTO` | `src/ui/desktop/engine_dashboard.py` | Sim (`QTimer`) | Não | [ ] Pendente |
| `SensibilidadeMercadoWidget` | 3 | `logging`, `math`, `threading`, `numpy`, `PySide6`, `analise_mercado`, `calendario_b3`, `market_data_source`, `ibov_composition_client`, `repository` | `src/ui/desktop/sensibilidade_mercado_widget.py` | Sim (`QThread`, `QTimer`, `threading.Lock`) | Não | [ ] Pendente |
| `FeriadosDialog` | 3 | `datetime`, `PySide6`, `theme` | `src/ui/desktop/feriados_dialog.py` | Sim (`QThread`) | Não | [ ] Pendente |
| `DividendosDialog` | 3 | `datetime`, `PySide6`, `theme` | `src/ui/desktop/dividendos_dialog.py` | Sim (`QThread`) | Não | [ ] Pendente |
| `BlacklistImportDialog` | 3 | `PySide6`, `repositories`, `parametro_operacional`, `theme` | `src/ui/desktop/blacklist_import_dialog.py` | Não | Não | [ ] Pendente |
| `TaxaAluguelDialog` | 3 | `PySide6`, `repositories`, `theme` | `src/ui/desktop/taxa_aluguel_dialog.py` | Sim (`QThread`) | Não | [ ] Pendente |
| `WhitelistBox4PDialog` | 3 | `PySide6`, `repositories`, `parametro_operacional`, `theme` | `src/ui/desktop/whitelist_box4p_dialog.py` | Não | Não | [ ] Pendente |
| `CalendarioResultadosDialog` | 3 | `datetime`, `PySide6`, `theme` | `src/ui/desktop/calendario_resultados_dialog.py` | Sim (`QThread`) | Não | [ ] Pendente |
| `EstudosCalendarioDialog` | 3 | `sqlite3`, `math`, `PySide6`, `calendario_b3`, `database`, `column_utils` | `src/ui/desktop/estudos_calendario_dialog.py` | Sim (`QTimer`) | Não | [ ] Pendente |

---

## Configurações Externas e Tipos Globais

### Fontes de Parâmetros de Mercado

| Parâmetro | Fonte | Local de Leitura | Fallback |
|---|---|---|---|
| `taxa_cdi` (CDI) | DB `parametros_operacionais` | `ParametroRepository.get_by_chave("taxa_cdi")` | `parametros_default.json` → `ParametroOperacional.defaults` (0.1425) |
| `fonte_market_data` | DB `parametros_operacionais` | `ParametroRepository.get_by_chave("fonte_market_data")` | JSON `"openfast"`, hardcoded `"profit"` |
| Taxas B3 (emolumentos, liquidação, registro, ISS, IR) | DB `parametros_operacionais` | `ParametroRepository.get_by_chave("taxa_*")` | `CalculadoraCustosB3` defaults (0.025%, 0.0275%, 0.01%, 0%, 15%) |
| Feriados B3 | DB `feriados_b3` | `FeriadoB3Repository` → `calendario_b3.carregar_do_banco()` | Hardcoded `FERIADOS_B3_PADRAO` (40 datas 2024-2026) + BrasilAPI |
| Credenciais opcoes.net.br | `.env` (raiz do projeto) | `load_dotenv()` em `opcoesnet_client.py:19` | — (obrigatórias para login) |
| `APPDATA` (path do DB) | Variável de ambiente Windows | `database.get_db_path()` → `%APPDATA%/Spreadhunter/spreadhunter.db` | `~/.local/share/Spreadhunter` |
| `SPREADHUNTER_QSETTINGS_*` | Variáveis de ambiente | `workspace_service.py:89-90` | QSettings default org/app |
| Janelas de volatilidade | DB `parametros_operacionais` | `ParametroRepository.get_by_chave("vol_janela_*")` | `parametros_default.json` |
| Cotação spot (yfinance) | Internet | `mercado_topbar.py:315`, `sensibilidade_mercado_widget.py:181` | — |
| Composição IBOV | `ibov_composition_client.py` (arquivo JSON ou hardcoded) | `config/spreadhunter_prioridade.json` | Top-50 hardcoded |
| Taxas de aluguel | InvestSite (web scraping) | `investsite_client.py` | — |

### Tipos Globais (Enums e Protocols)

| Tipo | Arquivo | Valores |
|---|---|---|
| `FieldName` | `market_data_source.py:5` | `STRIKE, LAST_PRICE, BID, ASK, STATUS, QTD_LAST, VOL_BID, VOL_ASK, BOOK_HEADER, HIGH, LOW, OPEN, CLOSE, VOLUME, VOLUME_FIN, VARIATION` |
| `ClassificacaoOp` | `oportunidade.py:5` | `BOX_1, SBTH_2, BOXSBTH_3, TP_OP` |
| `TipoEstrutura` | `estrutura_operacional.py:5` | `BOX_ITM_BASKET, BOX_3_PERNAS, SBTH` |
| `TipoOpcao` | `instrumento_opcional.py:6` | `AMERICANA (A), EUROPEIA (E)` |
| `Lado` | `perna_operacao.py:5` | `COMPRA (C), VENDA (V)` |
| `TipoExportacao` | `dtos.py:6` | `BASKET_ITM, LOG_OPERACAO` |
| `MarketDataSource` (Protocol) | `market_data_source.py:54` | 12 métodos + 3 atributos (`suporta_push`, `suporta_cab_skip`, `is_mock`) |
| `TipoColar` | `calculadora_colar.py` | `STRIKES_ABAIXO, STRIKES_ACIMA, TRADICIONAL` |
| `TipoColarCalendario` | `calculadora_colar_calendario.py` | `NEUTRO, CALL_SOBREPOSTO, PUT_SOBREPOSTO` |

### Estrutura do Banco (19 tabelas, exceto `sqlite_sequence`)

`instrumentos_base`, `parametros_operacionais`, `oportunidades`, `estruturas_operacionais`, `pernas_operacao`, `dividendos`, `feriados_b3`, `workspace_snapshots`, `historico_simulacoes`, `taxas_aluguel`, `calendario_resultados`, `mpp_cache_opcoesnet`, `mpp_score_estrutural`, `mpp_box_score`, `mre_recomendacao`, `mpp_snapshot`, `mpp_historico_distorcoes`, `mpp_spread_history`

> Nota: `historico_rejeicoes` (Fase 6 do plano de proteção de cauda) **não foi implementada** — não existe no schema atual.

### Pipeline do Worker (ordem de execução)

```
1. Geral (BOX/SBTH) → 2. Colares → 3. Collar Calendário → 4. Box 4P
→ 5. Put Ratio → 6. Manutenção (Onda 2 + background scan) → 7. Reconexão → 8. MPP
```

### Hotspots de Concorrência

| Módulo | Mecanismo | Risco |
|---|---|---|
| `MonitorWorker.run()` | `CoInitializeEx(COINIT_APARTMENTTHREADED)` + `QMutex`/`QWaitCondition` | Crash COM se omitido |
| `MercadoDataProvider._flush_buffer()` | Chamado fora do `QMutex` (COM lento) | Book=0 se esquecido em qualquer branch |
| `RTDProfit` | `threading.Lock` sobre cache + tópicos COM | Race condition em `ConnectData`/`RefreshData` |
| `OpenFastSocketAdapter` | `threading.Lock` + daemon reader thread | Corrupção de cache se lock ausente |
| `InstrumentoRepository` | `threading.Lock` de classe sobre `_cache_all` | Stale cache em multi-thread |
| `ParametroRepository` | `threading.Lock` per-chave com `_dict_lock` | Deadlock se lock hierarchy violada |

---

## Sumário de Cobertura

| Camada | Total Módulos | Com Testes | Parciais | Sem Testes |
|---|---|---|---|---|
| 0 — Kernel | 30 | 19 | 4 | 7 |
| 1 — Infraestrutura | 30 | 13 | 5 | 12 |
| 2 — Estratégias | 23 | 7 | 7 | 9 |
| 3 — UI | 39 | 11 | 2 | 26 |
| **Total** | **122** | **50** | **18** | **54** |

**Maiores lacunas (sem cobertura alguma):** `opcoesnet_client.py` (627 linhas, 0 testes), 6 use cases sem testes (`MonitorColaresUseCase`, `MonitorColaresCalendarioUseCase`, `MonitorBoxUseCase`, `MonitorPutRatioUseCase`, `MonitorVendidasUseCase`, `MonitorVendaCobertaUseCase`), `CalculadoraVetorizada` (0 testes), 4 repositórios sem testes (`DividendoRepository`, `FeriadoB3Repository`, `CalendarioResultadosRepository`, `HistoricoSimulacoesRepository`), 5 providers sem testes (`MercadoEstruturalProvider`, `FeriadosB3Provider`, `CalendarioResultadosCVM`, `CalendarioResultadosWebWallet`, `DividendosStatusInvest`).
