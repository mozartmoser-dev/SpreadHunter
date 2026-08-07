# InstrumentoOpcional

## Propósito

Entidade central que mapeia um par de opções (CALL, PUT) para um ativo + vencimento
na B3. É a tabela `instrumentos_base`: sem ela, nenhum use case consegue montar
estratégias porque não sabe quais opções existem para cada ativo.

`dataclass` com `slots=True`, imutável estruturalmente (apenas `id` e `strike` são
opcionais e podem ser populados tardiamente). Strike NUNCA é fonte de verdade —
vem do RTD em tempo real (regra #1 do AGENTS.md).

## Contrato (Requisitos)

### `InstrumentoOpcional(ativo, cod_put, cod_call, vencimento, tipo_opcao, ...)`

**Garante:**
1. Chave natural implícita: `(ativo, cod_put)` — cada PUT identifica unicamente
   um instrumento. A CALL correspondente está em `cod_call`.
2. `vencimento` é `datetime.date` (não string), serializado via `.isoformat()`
   pelo repositório.
3. `tipo_opcao` é o enum `TipoOpcao` (`"A"` ou `"E"`). Regra de negócio: ler
   `MOD` apenas da CALL (PUTs B3 são sempre Europeias).
4. `strike: float | None` — opcional, populado via API `OptionsChain` no import
   e persistido como fallback. NUNCA usado como fonte primária de cálculo.
5. `id: int | None` — populado pelo repositório após `INSERT` (`cursor.lastrowid`).
6. `created_at: datetime | None` — opcional, pode não existir em schemas antigos.

### `dias_ate_vencimento` (property)

**Garante:**
1. Calcula `(vencimento - date.today()).days`.
2. Se `vencimento is None`, retorna `0`.
3. Resultado nunca negativo: `max(delta, 0)`.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|-------- |----------------|-----|
| `dataclasses` | `dataclass` | Decorador da classe |
| `datetime` | `date`, `datetime` | Tipos dos campos `vencimento`, `created_at` |
| `enum` | `Enum` | `TipoOpcao` (definido no mesmo arquivo) |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 27 |
| Classes | 2 (InstrumentoOpcional + TipoOpcao no mesmo arquivo) |
| Métodos/Funções | 1 property (dias_ate_vencimento) |
| Complexidade ciclomática estimada | Baixa |
| Testes | Sim (indireto — fixtures `instrumento_repo`, `populated_db`) |

## Notas

- [2026-05-11 via git log] módulo criado. Última modificação: 2026-07-06.
- **POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão:** `dias_ate_vencimento` verifica
  `if self.vencimento is None` com fallback `return 0`, mas o tipo do campo é `date`
  (não `date | None`). Ou o tipo deveria ser `date | None`, ou a verificação é
  código morto (a menos que alguém viole o tipo em runtime, possível já que
  `slots=True` não impõe type-checking).
- O campo `strike` é populado pelo importador (`importflash.py`) via API
  `OptionsChain`, mas o `InstrumentoRepository.save()` não o persiste — a coluna
  existe no schema mas o INSERT do repositório não a inclui. Isso é intencional:
  strike vem do RTD em tempo real (regra #1 do AGENTS.md).
- `slots=True` impede adição dinâmica de atributos — relevante para testes que
  tentem mockar campos inexistentes.
