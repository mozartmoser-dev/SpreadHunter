# MonitorVendaCobertaUseCase

## Propósito

Scanner de Venda Coberta — a estratégia mais simples: comprar ação + vender CALL.
Dois modos: `varrer()` (venda coberta tradicional) e `varrer_comprada()` (taxa comprada,
onde a CALL está ITM e o retorno é tratado como renda fixa).

Monitora o book para encontrar CALLs com prêmio que gere %CDI ≥ `premio_risco_venda_coberta`
(ou `premio_risco_taxa_comprada` para o modo comprada), considerando custos B3 e IR.

## Dependências

- `src.application.dtos.dtos_venda_coberta` → `OportunidadeVendaCoberta`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`

## Cobertura de Teste

**Status: 0 testes.** Inventory.md classifica como "Não".
