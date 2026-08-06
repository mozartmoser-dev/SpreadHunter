# MonitorColaresUseCase

## Propósito

Orquestrador do scanner de Colar Protetivo Tradicional. Itera sobre `inst_map`, extrai
dados do RTD/OpenFast, classifica pares CALL/PUT por tipo (STRIKES_ACIMA, STRIKES_ABAIXO,
TRADICIONAL), e chama `CalculadoraColar.calcular()` para cada par.

Aplica filtros de liquidez (QUL mínimo), ranking com score CDI × Pop × Risco, e
suporta dois modos de leitura: via RTD Profit (COM) ou via `dados_mercado` (OpenFast).

## Dependências

- `src.domain.services.calculadora_colar` → `CalculadoraColar`, `ResultadoColar`, `RiscoLeilao`, `TipoColar`
- `src.domain.services.market_data_source` → `FieldName`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`

## Cobertura de Teste

**Status: 0 testes.** Inventory.md classifica como "Não".
