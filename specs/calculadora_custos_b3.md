# CalculadoraCustosB3

Calculadora de custos operacionais da B3 (emolumentos, liquidação, registro, ISS, IR).
Usada por todas as calculadoras de estratégia para descontar custos de corretagem
dos prêmios e preços de ativos.

## Contrato (Requisitos)

### `__init__(taxa_emolumento=None, taxa_liquidacao=None, taxa_ir=None, taxa_registro=None, iss=None)`
**Garante:**
1. Se `None`, usa constantes de classe:
   - `TAXA_EMOLUMENTO_OPCAO = 0.000250` (0.025%)
   - `TAXA_LIQUIDACAO_OPCAO = 0.000275` (0.0275%)
   - `TAXA_REGISTRO_OPCAO = 0.000100` (0.01%)
   - `ISS_PADRAO = 0.0`
   - `TAXA_IR_PADRAO = 0.15` (15% swing trade)
2. Sobrescrita por parâmetro permite customização (ex: testes com taxas zeradas).

### `taxa_total() -> float`
**Garante:**
1. Soma emolumento + liquidação + registro + ISS para opções.
2. Resultado típico: `0.000625` (0.0625%).

### `taxa_total_stock() -> float`
**Garante:**
1. Soma emolumento + liquidação + ISS (sem registro, que não incide sobre ações).
2. Resultado típico: `0.000525` (0.0525%).

### `custos_opcao(premio_medio, n_pernas=1, ida_e_volta=True) -> float`
**Garante:**
1. `taxa_total() * premio_medio * n_pernas * (2 if ida_e_volta else 1)`.
2. Premio médio é por opção (ex: R$1.50 para PUT a R$1.50).
3. Ida-e-volta padrão (`True`) assume que a posição pode ser fechada antes do vencimento
   (rolagem é comum). A B3 cobra dos dois lados independente de direção.

### `custos_opcao_vetor(premio_medio: np.ndarray, n_pernas=1, ida_e_volta=True) -> np.ndarray`
**Garante:**
1. Versão vetorizada de `custos_opcao` usando `numpy`.
2. `import numpy as np` é feito inline (lazy) — o módulo não importa numpy no topo.

### `custos_stock(preco, n_acoes=1, ida_e_volta=True) -> float`
**Garante:**
1. `taxa_total_stock() * preco * n_acoes * (2 if ida_e_volta else 1)`.
2. Usa `taxa_total_stock()` (sem registro).

### `custos_stock_vetor(preco: np.ndarray, n_acoes=1, ida_e_volta=True) -> np.ndarray`
**Garante:**
1. Versão vetorizada de `custos_stock`.

### `ajustar_ir(lucro_liquido: float) -> float`
**Garante:**
1. Se `lucro_liquido <= 0`, retorna `0.0` (não há IR sobre prejuízo).
2. Caso contrário, `lucro_liquido * taxa_ir` (15% default).

### `ajustar_ir_vetor(lucro_liquido: np.ndarray) -> np.ndarray`
**Garante:**
1. `np.where(lucro_liquido > 0, lucro_liquido * taxa_ir, 0.0)`.

### `calcular_custos_vendida(*, preco_ativo, premio_medio_opcoes, n_pernas_opcoes, n_acoes=1) -> float`
**Garante:**
1. Custos combinados: `custos_opcao(...) + custos_stock(...)`, ambos com `ida_e_volta=True`.
2. Se `preco_ativo <= 0` ou `n_pernas_opcoes <= 0`, retorna `0.0`.
3. Keyword-only arguments (segurança contra inversão de parâmetros).

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| numpy | `np` | Import inline nos métodos vetorizados (não no topo) |

**Nenhum import no topo do arquivo** — classe pura com imports lazy de numpy.

**É dependência de:**
- 6 calculadoras: `calculadora_box.py`, `calculadora_box_sbth.py`, `calculadora_colar.py`, `calculadora_colar_calendario.py`, `calculadora_vetorizada.py`, `calculadora_put_ratio.py`
- 2 use cases: `monitor_vendidas.py`, `monitor_venda_coberta.py`
- `monitor_worker.py` (import direto + lazy)
- `monitor_colares_calendario.py`, `monitor_colares.py` (imports lazy)
- `tests/application/test_calcular_custos_vendida.py`

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 86 |
| Arquivo | `src/domain/services/calculadora_custos_b3.py` |
| Última modificação | 2026-07-09 |

## Notas
- 2026-07-09: última modificação (refatoração de interfaces).
- 2026-06-11: adição do método `calcular_custos_vendida`.
- 2026-06-09: criação do arquivo.
- Imports lazy de numpy nos métodos vetorizados — evita import desnecessário se só usar métodos escalares.
- Constantes de classe como fallback; em produção os valores vêm de `parametros_operacionais` no banco (taxa_emolumento_pct, taxa_liquidacao_pct, taxa_registro_pct, taxa_iss_pct, taxa_ir_pct).
