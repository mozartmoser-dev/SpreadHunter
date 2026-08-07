# ElegibilidadePescaria

## Propósito

Filtro de elegibilidade para candidatos a estratégia de "pescaria" — operação com CALL ITM
(deep in-the-money) como substituta sintética do ativo à vista. O serviço aplica 5 critérios
sequenciais (básicos, strike, col31, oferta venda, spread) para determinar se um candidato
é elegível para montagem da estrutura.

**Papel real no sistema (descoberto via grep, 07/08/2026):** o `ElegibilidadePescaria` é um
serviço de domínio **sem callers em produção**. A busca por `ElegibilidadePescaria` e
`CandidatoPescaria` em todo o código-fonte retorna apenas:
- O próprio arquivo `elegibilidade_pescaria.py` (definição)
- `tests/test_fase2.py` (testes unitários)

Nenhum use case, worker, diálogo ou widget importa ou instancia esta classe em produção.
POSSÍVEL BUG — módulo implementado mas nunca integrado ao pipeline de monitoramento.
Pode ser código planejado para fase futura, ou a integração foi esquecida. O `MonitorWorker`
e os use cases de monitoramento (`monitor_box_use_case.py`, `monitor_colares_use_case.py`,
etc.) não referenciam este serviço. Aguardando revisão.

`CandidatoPescaria` é um dataclass de transporte com 9 campos que representam o estado
mínimo de uma CALL ITM para avaliação de elegibilidade.

## Contrato (Requisitos)

### `__init__(taxa_ganho: float, strike_max_pct: float = 0.70)`

**Garante:**
1. `taxa_ganho` é o percentual de ganho mínimo exigido (ex: `10.0` = 10%).
2. `strike_max_pct` é o teto do strike como fração do preço do ativo (default `0.70` = 70%).
   CALLs com strike > 70% do preço do ativo são rejeitadas (não suficientemente ITM).

### `filtrar_candidatos(candidatos, ativo_referencia, vencimento_referencia, strike_atm) -> list[CandidatoPescaria]`

**Garante:**
1. Aplica 5 critérios em sequência com short-circuit (`continue`): se qualquer critério
   falhar, o candidato é descartado e não chega aos critérios seguintes.
2. Ordem de avaliação: básicos → strike ITM → col31 → oferta venda → spread.
3. Retorna nova lista (não modifica a lista de entrada).
4. Critérios implementados como métodos privados (`_criterios_*`).

### `_criterios_basicos(c, ativo_ref, venc_ref) -> bool`

**Garante:**
1. `c.ativo == ativo_ref AND c.vencimento == venc_ref`.
2. Rejeita candidatos de ativo diferente ou vencimento diferente.
3. Comparação exata de strings — POSSÍVEL BUG se `vencimento` vier em formatos diferentes
   (ex: `"2026-08-21"` vs `"21/08/2026"`). Na prática, o campo `vencimento` é sempre
   serializado via `.isoformat()` pelo repositório, então o formato é consistente.

### `_criterio_strike_itm(c) -> bool`

**Garante:**
1. Se `c.preco_ativo <= 0`, rejeita (preço inválido).
2. Exige `strike_call_itm <= preco_ativo * strike_max_pct` (default: strike ≤ 70% do preço).
3. Se `strike_max_pct` foi configurado como `0.70`, uma CALL de strike R$10 com ativo a
   R$18 é elegível (`10 <= 12.6`), mas uma CALL de strike R$15 não é (`15 > 12.6`).

### `_criterio_col31(c) -> bool`

**Garante:**
1. Exige `col31_valor > 0` — o valor do colar 3:1 (indicador de oportunidade) deve ser positivo.

### `_criterio_oferta_venda(c) -> bool`

**Garante:**
1. Exige `of_venda_call > 0` — a CALL ITM precisa ter oferta de venda (bid) no book.

### `_criterio_spread(c, strike_atm) -> bool`

**Garante:**
1. Calcula `spread = strike_atm - strike_call_itm`.
2. Se `spread <= 0`, rejeita (CALL ITM com strike acima do ATM não faz sentido para pescaria).
3. Calcula `valor_limite = spread * (100 - taxa_ganho) / 100`.
4. Exige `col31_valor >= valor_limite` — o valor do colar 3:1 deve cobrir pelo menos
   `(100 - taxa_ganho)%` do spread.

### `calcular_valor_limite(strike_atm, strike_itm) -> float`

**Garante:**
1. Método público utilitário (não chamado por `filtrar_candidatos()`, exposto para uso externo).
2. `spread = strike_atm - strike_itm`.
3. Se `spread <= 0`, retorna `0.0`.
4. Retorna `spread * (100 - taxa_ganho) / 100`.

## Decisões Tomadas

### 1. Critérios como métodos privados encadeados com short-circuit

**Porquê:** Cada critério é uma condição independente de rejeição. Encadear com
`continue` dentro de um loop evita alocações intermediárias (não cria listas parciais)
e torna a ordem de avaliação explícita. A separação em métodos privados permite
testar critérios individuais (embora os testes atuais só testem via `filtrar_candidatos()`).

### 2. `CandidatoPescaria` como dataclass separada (não como atributos soltos)

**Porquê:** A estrutura tem 9 campos que viajam juntos entre a fonte de dados
(o use case que popula os candidatos) e o filtro. Uma dataclass com `slots=True`
é mais eficiente que um dict e fornece type hints. O `CandidatoPescaria` é um
DTO puro, sem comportamento.

**Trade-off:** Como o módulo não é usado em produção, a dataclass existe apenas
para os testes. Se a integração acontecer, o use case chamador precisará construir
instâncias de `CandidatoPescaria` a partir dos dados de mercado.

### 3. `strike_max_pct` com default 0.70

**Porquê:** 70% do preço do ativo é um threshold conservador para considerar uma
CALL como suficientemente ITM para substituição sintética. CALLs com strike entre
70% e 100% do preço têm delta menor que 1 e mais extrínseco, reduzindo a eficácia
da estratégia.

### 4. `calcular_valor_limite()` como método público separado

**Porquê:** Permite que o chamador calcule o valor limite sem precisar construir
um `CandidatoPescaria` completo. Útil para exibição de thresholds na UI ou para
pré-filtragem antes de criar os candidatos.

## Decisões Rejeitadas

### 1. Usar `strike_max_pct` como parâmetro de banco

Rejeitado porque o valor é passado no construtor (`__init__`) e pode ser configurado
pelo chamador. Se o use case que integrar este serviço quiser parametrizar, basta
ler o parâmetro do banco e passar no construtor. O serviço em si não precisa conhecer
o repositório.

### 2. Retornar razão da rejeição junto com a lista de elegíveis

Rejeitado para manter a API simples. Se necessário para debugging, pode-se adicionar
um parâmetro `debug=False` que popula uma lista de rejeições. Não implementado porque
o módulo não tem callers em produção.

### 3. Unificar `calcular_valor_limite()` com `_criterio_spread()`

Rejeitado porque `calcular_valor_limite()` é parte da API pública (pode ser chamado
externamente para UI/cálculos) enquanto `_criterio_spread()` é lógica interna de
filtragem. Mantê-los separados evita duplicação mas preserva a distinção público/privado.

## Dependências

- `dataclasses` — stdlib
- **Não depende de:** entidades de domínio, repositórios, banco de dados, RTD/OpenFAST

**É dependência de:**
- `tests/test_fase2.py` (TestElegibilidadePescaria — 5 testes)
- **Nenhum código de produção** — POSSÍVEL BUG, módulo não integrado

## Cobertura de Teste

**Status: 5 testes em `tests/test_fase2.py`** (classe `TestElegibilidadePescaria`)

| Teste | Cobre |
|---|---|
| `test_candidato_elegivel` | Candidato válido passa em todos os critérios |
| `test_candidato_ativo_diferente` | Rejeição por ativo diferente do referência |
| `test_candidato_strike_nao_itm` | Rejeição por strike > 70% do preço (strike=15, preço=18, limite=12.6) |
| `test_candidato_sem_oferta_venda` | Rejeição por `of_venda_call == 0` |
| `test_calcular_valor_limite` | Cálculo do valor limite isolado |

**Lacunas conhecidas (não cobertas):**
- Critério `_criterio_col31()` com `col31_valor <= 0` — 0 testes diretos
- Critério `_criterio_spread()` com spread insuficiente — 0 testes diretos
- `strike_max_pct` customizado (não-default) — 0 testes
- `taxa_ganho` diferente de 10% — 0 testes
- `preco_ativo <= 0` no critério strike — 0 testes
- `spread <= 0` no critério spread — 0 testes
- `vencimento` diferente no critério básico — 0 testes
- **Integração com use case — 0 testes.** Confirmado via grep: zero callers em produção.
