# ExportarResultado (DTO)

## Propósito

DTO que transporta os dados de uma operação exportada para o PNT (Profit)
ou para log. Contém a estrutura completa (pernas), indicadores financeiros
(% ganho, % CDI), dados da boleta gerada e timestamp de exportação.

É o output do `ExportarOperacaoUseCase` e a entrada para o `PNTIntegration`
(automação de interface gráfica do Profit).

## Contrato (Requisitos)

### `ExportarResultado(estrutura_id, tipo_exportacao, ativo, strike, ...)`

**Garante:**
1. `estrutura_id: int` — FK para `estruturas_operacionais.id`.
2. `tipo_exportacao: str` — tipo de exportação (ex: `"BASKET_ITM"`,
   `"LOG_OPERACAO"`).
3. `ativo: str` — ticker do ativo-objeto.
4. `strike: float` — strike de referência da operação.
5. `pernas: list[dict]` — lista de pernas, cada dict com chaves da boleta.
   `field(default_factory=list)`.
6. `classificacao: str` — classificação da oportunidade (default `""`).
7. `operacao: str` — descrição textual (default `""`).
8. `pct_ganho: float` — percentual de ganho (default `0.0`).
9. `pct_cdi: float` — percentual do CDI (default `0.0`).
10. `dias: int` — dias até vencimento (default `0`).
11. `exportado_em: str` — timestamp de exportação (default `""`).
12. `boleta: dict` — dados completos da boleta para o PNT.
    `field(default_factory=dict)`.
13. `oportunidade_id: int` — FK para `oportunidades.id` (default `0`).

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass`, `field` | Decorador, `default_factory` |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 227 (compartilhado com 4 outros DTOs + 1 enum) |
| Classes | 1 dataclass |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Baixa |
| Testes | Parcial (indireto via `ExportarOperacaoUseCase`) |

## Notas

- [2026-05-11 via git log] criado. Última modificação: 2026-07-29.
- `boleta: dict` é um campo livre que contém a estrutura formatada para o PNT
  (Profit). O formato exato é definido pelo `PNTIntegration`, não por este DTO.
- `exportado_em` é `str` (não `datetime`) — o formato exato depende do
  consumidor. Consistente com o fato de que este DTO é serializado para JSON
  antes de chegar ao PNT.
- `oportunidade_id` default `0` (não `None`) — `0` é usado como sentinela para
  "sem vínculo com oportunidade" (ex: exportações manuais de baskets).
