# MonitorColaresCalendarioUseCase

## Propósito

Orquestrador do scanner de Collar Calendário. Itera sobre a whitelist de ativos, carrega
dados históricos de IV do opcoes.net.br, pareia CALLs e PUTs do `inst_map` por distância
de strike + DTE, e chama `CalculadoraColarCalendario.calcular()` para cada par viável.

É o **único call site de produção** da `CalculadoraColarCalendario` (linha 360).

## Dependências

- `src.domain.services.calculadora_colar_calendario` → `CalculadoraColarCalendario`, `ResultadoColarCalendario`, `TipoColarCalendario`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.market_data_source` → `FieldName`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.integrations.opcoesnet_client` → `OpcoesNetClient`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`

## Cobertura de Teste

**Status: 0 testes diretos.** 56 testes da calculadora (`test_calculadora_colar_calendario.py`) cobrem
o cálculo, mas não o use case (pareamento, filtro DTE, cache IV, whitelist).
