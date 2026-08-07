# TipoOpcao (enum)

## Propósito

Enum simples que classifica o modelo de exercício de uma opção B3: Americana
(pode ser exercida a qualquer momento até o vencimento) ou Europeia (exercício
apenas na data de vencimento).

É usado como campo do `InstrumentoOpcional` e lido pelo repositório como
`.value` (`"A"` ou `"E"`). Regra de negócio crítica: **ler `MOD` apenas da CALL** —
PUTs B3 são sempre Europeias (`"E"`), independentemente do que o ticker sugira.

## Contrato (Requisitos)

### `TipoOpcao.AMERICANA`

**Garante:**
1. Valor serializado: `"A"`.
2. Opção pode ser exercida a qualquer momento até o vencimento.

### `TipoOpcao.EUROPEIA`

**Garante:**
1. Valor serializado: `"E"`.
2. Opção só pode ser exercida na data de vencimento.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `enum` | `Enum` | Classe base |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 27 (compartilhado com InstrumentoOpcional) |
| Classes | 1 enum (2 membros: AMERICANA, EUROPEIA) |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Mínima |
| Testes | Sim (indireto via fixtures e testes de repositório) |

## Notas

- [2026-05-11 via git log] criado junto com `InstrumentoOpcional`. Última modificação: 2026-07-06.
- Definido no mesmo arquivo que `InstrumentoOpcional` (`src/domain/entities/instrumento_opcional.py`).
- O scanner Box 4P usa `box_soh_europeia=1` (default) para exigir que a CALL K1
  seja Europeia. Se a CALL for Americana, o par é rejeitado. `box_soh_europeia=0`
  desabilita essa verificação (aceita CALL Americanas).
- A distinção Americana/Europeia NUNCA é inferida do código B3 (sufixo do ticker) —
  vem exclusivamente do campo `MOD` retornado pelo RTD/OpenFast.
