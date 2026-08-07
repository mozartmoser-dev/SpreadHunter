# EstruturaOperacional

## Propósito

Entidade que representa uma estrutura operacional montada a partir de uma
oportunidade detectada. Armazena o tipo de estrutura (BOX ITM Basket,
BOX 3 Pernas, SBTH), os coeficientes alvo e de mercado, e a taxa de ganho.

É a entidade "pai" de `PernaOperacao`: uma estrutura tem N pernas
(relação 1:N via `estrutura_id` FK).

## Contrato (Requisitos)

### `EstruturaOperacional(oportunidade_id, tipo, coefic_alvo, coefic_mercado, taxa_ganho, ...)`

**Garante:**
1. `oportunidade_id: int | None` — FK para `oportunidades.id`. Pode ser `None`
   se a estrutura não estiver vinculada a uma oportunidade.
2. `tipo: TipoEstrutura` — enum: `BOX_ITM_BASKET`, `BOX_3_PERNAS`, `SBTH`.
3. `coefic_alvo: float` — coeficiente teórico (valor "justo" calculado).
4. `coefic_mercado: float` — coeficiente observado no mercado (book real).
5. `taxa_ganho: float` — taxa de ganho calculada (diferença entre alvo e mercado).
6. `id: int | None` — populado pelo repositório após INSERT.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass`, `field` | Decorador, `default_factory` (não usado nos fields, mas importado) |
| `enum` | `Enum` | `TipoEstrutura` (definido no mesmo arquivo) |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 18 |
| Classes | 2 (EstruturaOperacional + TipoEstrutura no mesmo arquivo) |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Baixa |
| Testes | Sim (indireto via `TestEstruturaRepository` e fixtures) |

## Notas

- [2026-05-11 via git log] módulo criado. Última modificação: 2026-06-16.
- `field` é importado mas não usado nos campos da dataclass — é mantido
  por consistência com o padrão do arquivo `oportunidade.py`.
- `coefic_alvo` vs `coefic_mercado`: a diferença entre eles determina se
  a estrutura é lucrativa. O cálculo exato está nas montadoras
  (`montadora_box_itm.py`, etc.), não nesta entidade.
- A FK `oportunidade_id` é nullable — estruturas podem existir sem vínculo
  com oportunidade (ex: baskets gerados manualmente).
