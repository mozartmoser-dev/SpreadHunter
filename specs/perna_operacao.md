# PernaOperacao

## Propósito

Entidade que representa uma perna individual de uma estrutura operacional.
Cada estrutura (`EstruturaOperacional`) tem N pernas, onde cada perna
especifica: qual ativo/opção negociar, lado (compra/venda), quantidade,
profundidade no book e ordem de execução.

É a unidade atômica de execução: o que o PNT (Profit) ou outro executor
recebe para enviar ordens ao mercado.

## Contrato (Requisitos)

### `PernaOperacao(estrutura_id, codigo, lado, quantidade, profundidade, ordem, ...)`

**Garante:**
1. `estrutura_id: int` — FK para `estruturas_operacionais.id`.
2. `codigo: str` — código de negociação B3 (ex: `"PETRA50"`, `"PETR4"`).
3. `lado: Lado` — enum: `COMPRA` (`"C"`) ou `VENDA` (`"V"`).
4. `quantidade: int` — número de contratos/ações.
5. `profundidade: int` — nível do book a consumir. Valores positivos = ASK
   (você paga), negativos = BID (você recebe). Convenção: `1` = primeira
   oferta de venda, `-1` = primeira oferta de compra.
6. `ordem: int` — sequência de execução (1-based). Pernas com mesma ordem
   podem ser executadas em paralelo.
7. `id: int | None` — populado pelo repositório após INSERT.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass` | Decorador da classe |
| `enum` | `Enum` | `Lado` (definido no mesmo arquivo) |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 18 |
| Classes | 2 (PernaOperacao + Lado no mesmo arquivo) |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Baixa |
| Testes | Sim (indireto via `TestPernaRepository` e fixtures) |

## Notas

- [2026-05-11 via git log] módulo criado. Última modificação: 2026-06-16.
- A convenção de `profundidade` (positivo = ASK/venda, negativo = BID/compra)
  é consistente com a regra #6 do AGENTS.md (coerência do book).
- `ordem` permite execução sequencial ou paralela: pernas com mesma ordem
  podem ser enviadas simultaneamente ao mercado.
- O campo `codigo` aceita tanto códigos de opções (ex: `"PETRA50"`) quanto
  tickers de ações (ex: `"PETR4"`) — a validação do formato é responsabilidade
  da montadora, não desta entidade.
