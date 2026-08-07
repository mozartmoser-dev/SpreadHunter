# BasketGerada (DTO)

## Propósito

DTO que transporta uma basket (cesta de pernas) gerada por uma montadora
de estruturas (ex: `MontadoraBoxItm`) para o serviço de exportação
(`ExportarOperacaoUseCase`) ou para a UI.

Contém os dados mínimos para identificar a estrutura e suas pernas: tipo,
ativo, strikes de referência e coeficientes de avaliação.

## Contrato (Requisitos)

### `BasketGerada(estrutura_id, tipo, ativo, strike_atm, strike_itm, ...)`

**Garante:**
1. `estrutura_id: int` — FK para `estruturas_operacionais.id`.
2. `tipo: str` — tipo da estrutura (ex: `"BOX_ITM_BASKET"`, `"SBTH"`).
3. `ativo: str` — ticker do ativo-objeto.
4. `strike_atm: float` — strike da opção ATM (at-the-money) de referência.
5. `strike_itm: float` — strike da opção ITM (in-the-money) de referência.
6. `pernas: list[dict]` — lista de pernas, cada uma como dict com chaves
   `codigo`, `lado`, `quantidade`, `profundidade`, `ordem`.
   `field(default_factory=list)`.
7. `coefic_alvo: float` — coeficiente teórico (default `0.0`).
8. `coefic_mercado: float` — coeficiente de mercado (default `0.0`).

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
| Testes | Não (sem cobertura direta) |

## Notas

- [2026-05-11 via git log] criado. Última modificação: 2026-07-29.
- `pernas` é `list[dict]`, não `list[PernaOperacao]` — isso evita acoplamento
  com a entidade de domínio e permite que o DTO trafegue entre camadas sem
  dependência da camada de persistência.
- `strike_atm` e `strike_itm` são strikes de referência para o basket,
  não necessariamente os strikes exatos das pernas — as pernas podem usar
  strikes derivados (ex: interpolação).
- Este DTO é efêmero: criado pela montadora, consumido pelo exportador,
  não persiste no banco.
