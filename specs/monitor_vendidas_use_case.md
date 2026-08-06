# MonitorVendidasUseCase

## Propósito

Scanner de operações VENDIDAS (BOX e SBTH vendidos). Monitora o book para detectar
oportunidades onde o crédito recebido na venda de BOX/SBTH supera o CDI alvo.

Usa `inst_map` para localizar instrumentos, calcula `receb_box = bid_ativo + bid_put - ask_call`
e `receb_sbth = bid_ativo + bid_put`, e classifica viabilidade por `pct_cdi ≥ premio_risco_vendidas`.

Gera `OportunidadeVendida` (DTO separado da tabela principal).

## Dependências

- `src.application.dtos.dtos_vendida` → `OportunidadeVendida`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`

## Cobertura de Teste

**Status: 7 testes** (3 em `test_vendidas_column_persist.py` + 4 em `test_calcular_custos_vendida.py`).
Inventory.md classifica como "Não" (mas há testes).
