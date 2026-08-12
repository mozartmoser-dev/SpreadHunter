# MercadoDataProvider

Orquestrador central do pipeline de market data. Coordena o registro progressivo de instrumentos no RTD/OpenFast em três ondas: Onda 0 (ativos prioritários), Onda 1 (cabeçalhos — strike + bid/ask básicos) e Onda 2 (detalhes completos — book completo, volumes). Implementa carga inteligente com skip por DTE, range de strike e filtro de semanais. Mantém cache de preços, controle de skip por ausência de book/ativo, e integração com mock data source.

## Contrato (Requisitos)

### `__init__(db_path=None, source=None)`
**Garante:**
1. Inicializa `InstrumentoRepository` e carrega prioridades do JSON de persistência.
2. Inicializa caches internos: `_chaves_registradas`, `_chaves_com_book`, `_chaves_detalhes_completos`, `_precos_ativo_cache`, `_cab_anterior`, `_dados_cache`.
3. Thread-safe via `QMutex` (não `threading.Lock` — requer integração com Qt event loop).
4. Chama `recarregar_parametros()` no final.

### `recarregar_instrumentos()`
**Garante:**
1. Reseta todas as flags de registro, caches e contadores.
2. Força re-registro de todos os instrumentos no próximo ciclo.
3. Limpa cache de preços, books, dados e cabeçalhos.
4. Invalida cache de inst_map.

### `recarregar_parametros()`
**Garante:**
1. Lê do banco (via `ParametroRepository`) os parâmetros de performance: `perf_carga_inteligente`, `perf_range_min`, `perf_range_max`, `perf_limite_meses`, `perf_dias_minimos`, `onda2_dte_min`, `onda2_dte_max`, `rtd_refresh_timeout_ms`, `perf_filtro_semanal`.
2. Se parâmetros mudaram após registro inicial, reseta flags de registro mantendo subscriptions já feitas, mas limpando caches de preços/books/Onda 2.

### `_registrar_ativos_prioritarios(instrumentos)`
**Garante:**
1. Registra apenas underlyings (LAST_PRICE, ASK, BID, STATUS) para obter preços de referência rapidamente.
2. Deduplica por ativo (`_ativos_registrados`).
3. Flusha o buffer via `_flush_buffer`.

### `_registrar_instrumento(inst, registros_acum=None) -> bool`
**Garante:**
1. Verifica se a chave `(ativo, cod_put)` já foi registrada.
2. Aplica filtros de skip: `_deve_pular_instrumento` (DTE, range de meses, semanal) e `_deve_pular_por_strike` (range de strike/preço).
3. Registra STRIKE (PUT + CALL), BOOK_HEADER, ASK (PUT), BID (CALL).
4. Correção de strike: para fontes COM (RTD), compara strike do banco com strike do RTD e usa o menor (ajuste pós-evento como ex-dividendo). Para push-based (OpenFast), o strike do banco é canônico.
5. Registra ativo se ainda não registrado (LAST_PRICE, ASK, BID, STATUS).
6. Acumula registros em `registros_acum` (batch) ou envia direto via `rtd.registrar_lista`.

### `_registrar_batch_inteligente(instrumentos, batch_size=2000) -> list`
**Garante:**
1. Processa instrumentos em lotes de `batch_size` a partir de `_registro_idx`.
2. Se `_registrado` já é True, retorna lista vazia (não reprocessa).
3. Após processar todos, marca `_registrado = True` (Onda 1 concluída).
4. Retorna lista acumulada de registros para flush externo.

### `_registrar_novos_entrantes() -> list`
**Garante:**
1. Background scan: percorre todos os instrumentos do banco em lotes de 2000.
2. Registra instrumentos que não estavam no cache (novos entrantes pós-importação).
3. Quando completa um ciclo, reseta o índice e loga total monitorado.

### `capturar_dados_mercado() -> dict[str, dict]`
**Garante:**
1. **Mock source**: se `source.is_mock`, usa `MockMarketDataProvider` para gerar dados sintéticos e retorna imediatamente.
2. **Onda 0**: se ativos não registrados, registra underlyings primeiro.
3. **Onda 1**: registra cabeçalhos (strike + bid/ask básicos) em lotes. Se houver prioridades (`_prioridade_set`), processa prioritários primeiro.
4. **Refresh**: chama `source.refresh()` para obter dados atualizados.
5. **Varredura**: itera sobre `_chaves_com_book`:
   - **Onda 2** (detalhes completos): para chaves em `_chaves_detalhes_completos`, lê book completo. Aplica CAB skip (Profit) ou dirty keys (OpenFast) para evitar releitura desnecessária.
   - **Onda 1** (dados básicos): para chaves só com cabeçalho, lê strike + OCP/OVD para colares.
6. **Cache de preço de ativo**: se ASK do ativo falhar, usa `_precos_ativo_cache` como fallback.
7. **Skip por ausência**: instrumentos sem preço de ativo por múltiplos ciclos são skipados temporariamente (`SEM_ATIVO_SKIP_CYCLES = 10`).
8. Thread-safe: todo o método roda sob `self._lock`.
9. Garante chamada a `self._flush_buffer()` em todos os branches que acumulam registros (Onda 0, Onda 1).

### `fazer_manutencao()`
**Garante:**
1. Detecta novos books: itera sobre `_chaves_registradas - _chaves_detalhes_completos`.
2. Verifica liquidez: OVD (ask da PUT) > 0, OCP (bid da CALL) > 0, ou CAB > 0.
3. Se detectar liquidez E DTE dentro do range `[onda2_dte_min, onda2_dte_max]`, registra detalhes completos (Onda 2).
4. Limite de 500 registros Onda 2 por ciclo de manutenção para não sobrecarregar o COM.
5. Controle de skip: instrumentos sem book são skipados por `_MAX_SEM_BOOK_SKIP` ciclos.
6. Background scan de novos entrantes (se prioridades ativas).
7. Salva prioridades se `_chaves_com_book` mudou.
8. Flushes de buffer (Onda 2 e background scan) são feitos FORA do lock para não segurar o mutex durante chamadas COM lentas.

### `get_engine_stats() -> dict`
**Garante:**
1. Retorna contagens: total de instrumentos, Onda 1, Onda 2, progresso, flag de stale (>3 ciclos sem dados ou >30s sem refresh).

### `_ler_instrumento_cache(inst, preco_ativo) -> DadosRTDInstrumento | None`
**Garante:**
1. Lê PUT, CALL e ativo em batch (um lock por símbolo).
2. Se todos os campos de oferta são None/vazios, retorna None.
3. Se strike ausente ou <= 0, retorna None.
4. Retorna `DadosRTDInstrumento` populado.

### `_flush_buffer(buffer, max_chunk=1000)`
**Garante:**
1. Envia buffer em chunks de até 1000 registros via `source.registrar_lista`.
2. Limpa o buffer após envio.
3. Loga duração se > 100ms.

### `_deve_pular_instrumento(inst) -> bool`
**Garante:**
1. Se carga inteligente desabilitada, retorna False.
2. Pula se DTE < `_dias_minimos`.
3. Pula se DTE > `_limite_meses * 30`.
4. Pula se `_filtro_semanal` ativo E código tem 'W' na penúltima posição.

### `_deve_pular_por_strike(inst) -> bool`
**Garante:**
1. Se carga inteligente desabilitada ou range é `[-0.5, 0.5]` (default), retorna False.
2. Calcula `ratio = (strike / preco_ativo) - 1`.
3. Retorna True se ratio fora de `[_range_min, _range_max]`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `os` | `os` | Manipulação de paths |
| `time` | `time` | Performance e timestamps |
| `datetime` | `date` | Cálculos de DTE |
| `PySide6.QtCore` | `QMutex` | Mutex Qt para thread-safety |
| `src.domain.entities.instrumento_opcional` | `InstrumentoOpcional` | Entidade de instrumento |
| `src.domain.services.market_data_source` | `FieldName`, `MarketDataSource` | Interface de fonte de dados |
| `src.infrastructure.persistence.repositories.repositories` | `InstrumentoRepository` | Leitura de instrumentos |
| `src.infrastructure.providers.rtd_config` | `DadosRTDInstrumento` | Dataclass de snapshot |
| `json` (runtime) | - | Carga/salva de prioridades |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 863 |
| Última modificação | 2026-08-07 |
| Classes | 1 (`MercadoDataProvider`) |

## Notas

- 2026-08-07 — última modificação.
- O módulo é o coração do pipeline de dados — coordena 3 ondas de registro, cache de preços, mock source, manutenção de books e background scan.
- **STALE Gate (Fase 1):** `capturar_dados_mercado` verifica frescor de pernas críticas (ativo.ASK/BID, cod_put.ASK/BID, cod_call.ASK/BID) via `_campo_stale`. Instrumentos com pernas stale são pulados no ciclo. Para fontes push-based (OpenFast), leituras usam `allow_stale=True`; polling-based mantêm leitura fresca.
- **`allow_stale`:** `_ler_campo_cache` e `_ler_campos` aceitam `allow_stale=True` para fontes push-based, retornando valor cacheado mesmo se velho — necessário porque push só notifica mudanças.
- **Parâmetros STALE:** `assinar_timestamp_openfast` e `stale_sinal_s` lidos do banco via `ParametroRepository` em `recarregar_parametros`. Controlam assinatura de TIME/TIMENEG e tolerância de idade entre pernas.
- A thread-safety usa `QMutex` em vez de `threading.Lock` porque este provider é usado dentro de `MonitorWorker` (QThread).
- A correção de strike (usar `min(strike_db, strike_rtd)`) só se aplica a fontes COM (RTD Profit). Para OpenFast, o strike do banco (OptionsChain API) é a fonte canônica.
- `_flush_buffer` é chamado em múltiplos pontos. A regra do AGENTS.md é observada em todos os caminhos.
- O mock source (`source.is_mock`) é um atalho que pula todo o pipeline de registro.
- Prioridades são persistidas em JSON (`spreadhunter_prioridade.json`).
