# TipoEstrutura (enum)

## Propósito

Enum que classifica o tipo de estrutura operacional montada pelo sistema.
Cada valor corresponde a uma estratégia de montagem diferente, com regras
próprias de seleção de pernas e coeficientes.

## Contrato (Requisitos)

### `TipoEstrutura.BOX_ITM_BASKET` (`"BOX_ITM_BASKET"`)

**Garante:**
1. Estrutura do tipo BOX com basket de opções ITM (in-the-money).
2. Montada pela `MontadoraBoxItm` (`src/domain/services/montadora_box_itm.py`).
3. Usa coeficientes de mercado para calcular o spread box.

### `TipoEstrutura.BOX_3_PERNAS` (`"BOX_3_PERNAS"`)

**Garante:**
1. Estrutura BOX com 3 pernas (variante simplificada, sem a 4ª perna sintética).
2. [motivo não documentado, confirmar com o autor] — não está claro no código
   atual se este tipo ainda é usado em produção ou é legado.

### `TipoEstrutura.SBTH` (`"SBTH"`)

**Garante:**
1. Estrutura do tipo SBTH (Synthetic Borrow Trade Hedge).
2. Combina compra de ativo + venda de CALL + compra de PUT para criar um
   empréstimo sintético de ações.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `enum` | `Enum` | Classe base |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 18 (compartilhado com EstruturaOperacional) |
| Classes | 1 enum (3 membros) |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Mínima |
| Testes | Sim (indireto via fixtures e `TestEstruturaRepository`) |

## Notas

- [2026-05-11 via git log] criado junto com `EstruturaOperacional`. Última modificação: 2026-06-16.
- Definido no mesmo arquivo que `EstruturaOperacional` (`src/domain/entities/estrutura_operacional.py`).
- `BOX_3_PERNAS` — [motivo não documentado, confirmar com o autor] não foi
  encontrada referência a este valor nos use cases ativos. Pode ser um tipo
  legado ou reservado para feature futura.
- Os valores do enum são usados como chaves de serialização no banco e como
  identificadores nos DTOs (`BasketGerada.tipo`, `ExportarResultado.tipo_exportacao`).
