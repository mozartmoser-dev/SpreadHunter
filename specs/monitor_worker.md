# MonitorWorker

## Propósito

QThread central que coordena o pipeline completo de varredura de oportunidades em tempo real. Executa 7 estágios sequenciais a cada ciclo (3s default): Manutenção → Monitor Geral → Colares → Collar Calendário → Box 4P → Put Ratio → Reconexão → MPP. Gerencia `MercadoDataProvider`, reconexão da fonte de dados (Profit RTD/OpenFast), e emite resultados para a UI via sinais Qt. Suporta pausa/retomada com `QMutex`/`QWaitCondition`.

## Contrato (Requisitos)

### `run()`
**Garante:**
1. Inicializa COM (`CoInitializeEx(COINIT_APARTMENTTHREADED)`) se a fonte de dados for Profit (não OpenFast nem mock).
2. Cria `MercadoDataProvider` com a fonte configurada no banco (`fonte_market_data`).
3. Subscreve futuros (WIN, WDO) via `_subscrever_futuros(rtd)`.
4. Loop principal: dorme `_interval_ms` (mínimo 2000ms) entre ciclos; respeita `_paused` via `QWaitCondition`.
5. Pipeline sequencial: 0. Manutenção → 1. Geral → 2. Colares → 3. Collar Calendário → 4. Box → 5. Put Ratio → 6. Reconexão → 7. MPP.
6. Profiling: escreve métricas de tempo por estágio em arquivo TSV (`%TEMP%/spreadhunter_profile.tsv`).
7. Verifica integridade de parâmetros uma única vez no primeiro ciclo (`_verificacao_integridade_feita`).
8. Ao finalizar: chama `rtd.desconectar()` e `CoUninitialize()` (se COM foi inicializado).

### `pausar()` / `retomar()`
**Garante:**
1. `pausar()`: seta `_paused = True`.
2. `retomar()`: limpa `_paused`, tenta reconectar a fonte se indisponível, emite `rtd_status`, acorda a wait condition.

### `parar()`
**Garante:**
1. Seta `_running = False`, limpa `_paused`, acorda a wait condition.
2. Aguarda a thread terminar (`wait(6000)` — 6 segundos).
3. Se timeout, força `desconectar()` na fonte.

### `recarregar_parametros()`
**Garante:**
1. Propaga `recarregar_parametros()` para todos os 7 use cases + `MercadoDataProvider`.
2. Invalida cache do `ParametroRepository` do MPP.
3. Re-lê `mpp_habilitado` do banco e emite `mpp_status_changed` se o estado mudou.

### `recarregar_instrumentos()`
**Garante:**
1. Invalida `InstrumentoRepository.invalidate_cache()` (cache de classe).
2. Propaga `recarregar_instrumentos()` para o `MercadoDataProvider`.
3. Reseta `_mpp_carga_completa = False` e emite `mpp_status_changed(False)`.

### `_processar_monitor_geral(rtd)`
**Garante:**
1. Captura dados de mercado via `_mercado_provider.capturar_dados_mercado()`.
2. Armazena em `_ultimo_dados_mercado` (compartilhado com colares, calendário, box, put ratio).
3. Varre oportunidades (venda coberta + vendidas + geral) com `PipelineTracker`.
4. Filtra classificações "TP.Op" se `_mostrar_tp_op == False`.
5. Emite `oportunidades_atualizadas`, `oportunidades_vendidas_atualizadas`, `oportunidades_coberta_atualizadas`.
6. Salva snapshots de pipeline (`_snapshot_pipeline()`).

### `_processar_otimizado(resultados, tipo_estrategia, pipeline_tracker)`
**Garante:**
1. Para cada resultado viável do tipo correto (Neutro p/ Calendário, Tradicional p/ Colar):
   - Gera variantes otimizadas via `CalculadoraCaudaAssincrona.processar_otimizado()`.
   - Filtra por CDI mínimo (`premio_risco` do banco).
   - Avalia proteção de cauda via `CalculadoraProtecaoCauda.avaliar()`.
   - Para Calendário: seleciona tail protect (`_selecionar_tail_protect`) com score probabilístico.
2. Lê 15+ parâmetros do banco (`otimizado_desvios_sigma`, `n_sigma_protecao`, `limite_protecao_pct`, `bwb_modo`, etc.).
3. Registra variantes no `HistoricoSimulacoesRepository`.
4. Retorna lista de `ResultadoColar` / `ResultadoColarCalendario` otimizados.

### `StrategyToggle`
**Garante:**
1. Controle thread-safe de scan cíclico com `QMutex`.
2. `deve_escanear(db_reader)`: incrementa ciclo, verifica `forcar` ou intervalo configurável (do banco, se `use_db_interval`).
3. `iniciar_auto()`: seta `auto=True`, `forcar=True`, `cycle=0`.
4. `parar_auto()`: reseta tudo.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `logging` | stdlib | Logging |
| `time` | stdlib | `perf_counter` |
| `math` | stdlib | `log(1 + taxa_cdi)` |
| `os` | stdlib | Path de profile |
| `psutil` | (importado, uso não localizado) | — |
| `PySide6.QtCore` | `QThread, Signal, QMutex, QWaitCondition` | Thread e sincronização |
| `src.application.dtos.dtos` | `EngineStatsDTO` | DTO de estatísticas |
| `src.application.use_cases.*` | 7 use cases | Varredura de estratégias |
| `src.domain.services.pipeline_tracker` | `PipelineTracker` | Rastreamento de pipeline |
| `src.domain.services.calculadora_cauda_assincrona` | `CalculadoraCaudaAssincrona, ResultadoCaudaAssincrona` | Variantes otimizadas |
| `src.domain.services.calculadora_protecao_cauda` | `CalculadoraProtecaoCauda, ResultadoProtecaoCauda` | Proteção de cauda |
| `src.domain.services.calculadora_colar_calendario` | `ResultadoColarCalendario, TipoColarCalendario` | Resultados calendário |
| `src.domain.services.calculadora_colar` | `ResultadoColar, TipoColar` | Resultados colar |
| `src.domain.services.calendario_b3` | `dc_to_du` | Dias corridos → úteis |
| `src.domain.services.calculadora_custos_b3` | `CalculadoraCustosB3` | Custos B3 |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository, InstrumentoRepository, HistoricoSimulacoesRepository` | Leitura de parâmetros e persistência |
| `src.domain.services.market_data_source` | `FieldName, criar_data_source` | Fonte de dados |
| `src.infrastructure.providers.mercado_data_provider` | `MercadoDataProvider` | Provider de mercado |

## Métricas

| Linhas | 1396 |
| Classes | 2 (`StrategyToggle`, `MonitorWorker`) |
| Testes | Parcial (testado indiretamente via `test_fase3.py`; sem testes unitários isolados para MonitorWorker) |

## Notas

- **Pipeline fixo, não configurável:** A ordem dos 7 estágios é hardcoded no `run()`. Adicionar/remover/reordenar estágios requer alteração de código.
- **_flush_buffer crítico:** O `MercadoDataProvider` é responsável por assinar opções. Se `_flush_buffer()` não for chamado em algum branch, opções nunca são assinadas → book=0. Este worker não chama `_flush_buffer` diretamente — delega ao provider.
- **`psutil` importado mas não usado:** O import `import psutil` no topo do arquivo não tem uso visível no código atual. [motivo não documentado, confirmar com o autor].
- **Conexão do `MonitorBoxUseCase` com MPP:** O `_monitor_box_uc` recebe `_monitor_mpp_uc` no construtor — box e MPP compartilham infraestrutura.
- **Profile TSV:** Escrito em `%TEMP%/spreadhunter_profile.tsv` a cada ciclo. Colunas: ciclo, dt_total, dt_monitor, dt_colar, dt_cal, dt_box, dt_put_ratio, dt_manut, dt_mpp, n_inst_book, n_onda2. Útil para diagnóstico de gargalos.
