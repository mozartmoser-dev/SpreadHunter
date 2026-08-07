# Lado (enum)

## Propósito

Enum que indica o lado de uma perna operacional: compra ou venda.
Usado exclusivamente como campo de `PernaOperacao`.

## Contrato (Requisitos)

### `Lado.COMPRA` (`"C"`)

**Garante:**
1. A perna é uma compra (envia ordem de compra ao mercado).

### `Lado.VENDA` (`"V"`)

**Garante:**
1. A perna é uma venda (envia ordem de venda ao mercado).

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `enum` | `Enum` | Classe base |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 18 (compartilhado com PernaOperacao) |
| Classes | 1 enum (2 membros) |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Mínima |
| Testes | Sim (indireto via fixtures e `TestPernaRepository`) |

## Notas

- [2026-05-11 via git log] criado junto com `PernaOperacao`. Última modificação: 2026-06-16.
- Definido no mesmo arquivo que `PernaOperacao` (`src/domain/entities/perna_operacao.py`).
- Os valores `"C"` e `"V"` são usados como serialização no banco (coluna `lado`).
- A convenção de lado é independente da convenção de profundidade: uma perna
  `COMPRA` com profundidade `1` significa "comprar na primeira oferta de venda
  (ASK)". Uma perna `VENDA` com profundidade `-1` significa "vender na primeira
  oferta de compra (BID)".
