# MonitorBoxUseCase

## Propósito

Scanner de Box de 4 pernas. Itera sobre pares de strikes do mesmo ativo+vencimento,
valida MOD da CALL (só Europeia se `box_soh_europeia=1`), e chama
`CalculadoraBox.calcular()` para cada par. Usa whitelist de ativos específica para Box 4P.

Diferente do `MonitorOportunidadesUseCase` (que faz BOX+SBTH combinado via vetorização),
este é focado exclusivamente em Box 4 pernas com validação de MOD.

## Dependências

- `src.domain.entities.instrumento_opcional` → `InstrumentoOpcional`, `TipoOpcao`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_box` → `CalculadoraBox`, `ResultadoBox`
- `src.domain.services.market_data_source` → `FieldName`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`, `TaxaAluguelRepository`

## Cobertura de Teste

**Status: 0 testes.** Inventory.md classifica como "Não".
