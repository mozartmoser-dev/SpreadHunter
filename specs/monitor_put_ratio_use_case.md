# MonitorPutRatioUseCase

## Propósito

Scanner de Put Ratio Spread. Itera sobre a whitelist, carrega IV histórico do opcoes.net.br,
extrai dados RTD para PUTs, testa múltiplas combinações de ratio (1x2, 2x3, 1x3, etc.)
para cada par de strikes, e chama `CalculadoraPutRatio.calcular()`.

Filtra por delta (K1 e K2 devem estar em faixas específicas), IV rank mínimo, e DTE.

## Dependências

- `src.domain.services.calculadora_put_ratio` → `CalculadoraPutRatio`, `ResultadoPutRatio`, `RATIOS_DEFAULT`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.market_data_source` → `FieldName`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.integrations.opcoesnet_client` → `OpcoesNetClient`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`

## Cobertura de Teste

**Status: 0 testes diretos.** 48 testes da calculadora (`test_calculadora_put_ratio.py`) cobrem o cálculo,
mas não o use case (pareamento, filtro delta, cache IV).
