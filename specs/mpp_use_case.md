# MPPUseCase

## Propósito

Motor de Priorização de Pescaria (MPP) — o módulo mais complexo do sistema (795 linhas,
28 métodos). Identifica oportunidades de Box Spread com distorções de preço no mercado,
calculando scores multi-fator (estrutural: OI + volume + curvatura IV; instantâneo:
paridade + spread + profundidade + book imbalance), com persistência temporal e bônus
histórico para distorções recorrentes.

Também inclui MRE (Motor de Recomendação de Execução) que sugere tamanho de lote baseado
em profundidade de book e IP (Índice de Periculosidade).

## Dependências

- `src.domain.entities.instrumento_opcional` → `TipoOpcao`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.market_data_source` → `FieldName`
- `src.infrastructure.persistence.database` → `get_connection`
- `src.infrastructure.persistence.repositories.repositories` → `ParametroRepository`

## Cobertura de Teste

**Status: 2 testes** em `test_mpp_instrumentos_mapa.py`. Inventory.md classifica como "Sim".
Lacuna massiva: 795 linhas, 28 métodos, 2 testes cobrindo apenas `_obter_instrumentos_mapa`.
