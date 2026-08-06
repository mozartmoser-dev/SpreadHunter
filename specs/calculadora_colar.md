# CalculadoraColar

## Propósito

Calculadora do Colar Protetivo Tradicional — a estratégia mais simples de proteção: compra
ação + compra PUT (piso) + vende CALL (teto). Diferente do Collar Calendário, ambas as
opções têm o **mesmo vencimento** e a PUT está abaixo do spot (OTM), criando um túnel de
payoff limitado.

É a estratégia "porto seguro" do sistema: só existe cenário de perda se a ação cair abaixo
do strike da PUT, e o lucro máximo é travado no strike da CALL. O retorno é calculado
como `(pior_retorno / custo_liquido) / CDI_periodo` — quanto maior o %CDI gerado no pior
cenário, melhor a operação.

Fornece também `black_scholes_call`/`black_scholes_put`/`calcular_iv` estáticos — uma
implementação independente de B&S (separada da `CalculadoraColarCalendario`) usada pelo
diálogo de calculadoras manuais (`calculadoras_dialog.py`).

## Contrato (Requisitos)

### `calcular(...) -> ResultadoColar | None`

**Garante:**
1. Retorna `None` se: `preco_ativo ≤ 0`, `dias ≤ 0`, `premio_put ≤ 0`, `premio_call ≤ 0`,
   ou `qtd_acao/call/put % 100 ≠ 0`.
2. **DIFERENTE do Collar Calendário:** retorna `None` se `preco_compra_ativo ≤ 0` —
   não faz fallback para `preco_ativo`. O preço de compra real (ask do book) é obrigatório.
3. Retorna `None` se `custo_liquido ≤ 0` (operação não pode ter custo negativo ou zero).
4. **Custo líquido** (capital empatado):
   ```
   custo_liquido = preco_compra * qtd_acao + premio_put * qtd_put - premio_call * qtd_call
   ```
   Unidade: R$ total do portfólio (já escala por qtd).
5. **Pior retorno** (PUT exercida, ação vendida a Kp):
   ```
   pior_retorno = strike_put * qtd_acao - custo_liquido
   ```
6. **Melhor retorno** (CALL exercida contra, ação vendida a Kc):
   ```
   melhor_retorno = strike_call * qtd_acao - custo_liquido
   ```
7. **Viabilidade:** `pct_cdi_bruto ≥ premio_risco_colar`, onde:
   ```
   pct_ganho_bruto = pior_retorno / custo_liquido
   pct_cdi_bruto = pct_ganho_bruto / cdi_periodo
   ```
   Usa retorno BRUTO (antes de B3/IR) para viabilidade — consistente com a regra de que
   leilão é identificado visualmente, não descartado automaticamente.
8. **Custos B3 e IR** calculados e expostos separadamente (bruto vs líquido vs líquido IR),
   mas o filtro de viabilidade usa o bruto.
9. **IV e PoP:** calcula `calcular_iv` para CALL e PUT (independentemente). Se IV convergir,
   calcula `pop_upside` (probabilidade de S > Kc no vencimento) e `pop_downside`
   (probabilidade de S < Kp) via N(d2). Se IV não convergir, `iv_call`/`iv_put` = 0.0 e
   `pop_*` = None.
10. **Classificação:** `classificar_tipo` por relação de preços:
    - `preco_ativo < Kp < Kc` → STRIKES_ACIMA (viés alta)
    - `Kp < Kc < preco_ativo` → STRIKES_ABAIXO (viés baixa)
    - caso contrário → TRADICIONAL (viés neutro)

### `calcular_risco_leilao(vov_put, voc_call, status_put, status_call) -> RiscoLeilao`

**Garante:**
1. Se qualquer status ≠ "Aberto" → ALTO.
2. Se `vov_put ≤ 0` ou `voc_call ≤ 0` → ALTO.
3. Se ambos ≥ `colar_risco_baixo_vov_min` → BAIXO.
4. Caso contrário → MÉDIO.

### `calcular_iv(S, K, T, r, preco, tipo_opcao) -> float | None` (static)

**Garante:**
1. Bracket adaptativo com até 20 iterações: começa em `[1e-8, 5.0]`, expande o limite
   superior se necessário (multiplica por 2), contrai o inferior se necessário (divide por 2,
   mínimo 1e-12).
2. Se o preço de mercado for essencialmente igual ao valor intrínseco (diferença < 1e-10),
   retorna `0.0` (não tenta `brentq` — opção sem valor temporal).
3. Usa `brentq` quando `fa * fb < 0` (sinal oposto nos extremos do bracket).
4. Se falhar após 20 iterações ou `brentq` não convergir, retorna `None`.

### `classificar_tipo(preco_ativo, strike_put, strike_call) -> TipoColar`

**Garante:**
1. `preco_ativo < Kp < Kc` → STRIKES_ACIMA.
2. `Kp < Kc < preco_ativo` → STRIKES_ABAIXO.
3. Caso contrário → TRADICIONAL.

### `black_scholes_call(S, K, T, r, sigma)` / `black_scholes_put(...)` (static)

**Garante:**
1. Se `T ≤ 0` ou `sigma ≤ 0`, retorna valor intrínseco: `max(S-K, 0)` para call, `max(K-S, 0)` para put.
2. B&S completo com `norm.cdf`.
3. **Implementação independente** da `CalculadoraColarCalendario.black_scholes` — ambas
   calculam a mesma fórmula, mas são code paths separados (sem compartilhamento de código).

### `calcular_probabilidade_upside(S, K, T, r, sigma)` / `downside(...)` (static)

**Garante:**
1. `pop_upside = N(d2)` — probabilidade de S > K (call ITM no vencimento).
2. `pop_downside = N(-d2)` — probabilidade de S < K (put ITM no vencimento).
3. `d2 = (ln(S/K) + (r - 0.5*σ²)*T) / (σ*sqrt(T))`.

## Decisões Tomadas

### 1. `preco_compra_ativo` obrigatório (sem fallback para `preco_ativo`)

**Porquê:** No Colar Tradicional, a ação é comprada no momento da montagem. O preço real
de compra é o ask do book (`of_venda_ativo`), não o último preço negociado. Usar
`preco_ativo` como fallback (como faz `CalculadoraColarCalendario`) subestimaria o custo
real e inflaria artificialmente o %CDI. A decisão de exigir `preco_compra_ativo > 0`
e retornar `None` se ausente é deliberada — sem ask do book, a operação não é executável.

### 2. Viabilidade usa %CDI BRUTO (antes de B3/IR)

**Porquê:** Custos B3 e IR são dedutíveis apenas no lucro, não no custo. Usar o retorno
líquido para filtrar viabilidade criaria um viés contra operações de baixo retorno nominal
(onde B3/IR consomem proporcionalmente mais). O bruto é o numerador correto para comparar
contra `premio_risco_colar`. Os valores líquidos são expostos para decisão do trader,
não para o filtro automático.

### 3. `calcular_iv` com bracket adaptativo (≠ `CalculadoraColarCalendario.implied_volatility`)

**Porquê:** O `brentq` puro com intervalo fixo `[1e-6, 5.0]` (usado em `CalculadoraColarCalendario`)
pode falhar quando a função não muda de sinal nos extremos (ex: opção deep ITM/OTM com
spread bid-ask largo). O bracket adaptativo tenta expandir/contrair os limites por até 20
iterações antes de desistir. As duas calculadoras têm implementações separadas de IV por
razões históricas — foram desenvolvidas independentemente e nunca unificadas.
[motivo não documentado no código, confirmar com o autor] para não haver uma única
implementação canônica de IV no sistema.

### 4. `black_scholes_call`/`black_scholes_put` separados da `CalculadoraColarCalendario`

**Porquê:** A `CalculadoraColarCalendario` tem um único `black_scholes(S, K, T, r, sigma, option_type)`
com parâmetro `option_type`. A `CalculadoraColar` tem dois métodos separados
(`black_scholes_call`, `black_scholes_put`). Não há reuso de código entre elas —
[motivo não documentado no código, confirmar com o autor].

### 5. Risco de leilão classificado mas não bloqueia viabilidade

**Porquê:** Mesmo com status "Fechado" ou VOV/VOC zerado, a operação pode ser viável
financeiramente. O campo `risco_leilao` e `em_leilao` são informativos para o trader
(identificação visual na UI), não critérios de rejeição. O filtro `viavel` depende apenas
de `pct_cdi_bruto ≥ premio_risco_colar`.

## Decisões Rejeitadas

### 1. Unificar B&S com `CalculadoraColarCalendario`

Rejeitado na prática (nunca implementado). As duas implementações coexistem com
assinaturas diferentes (`option_type: str` vs métodos separados). O custo de unificar
seria baixo (a fórmula é a mesma), mas nenhum commit registra essa tentativa.
[motivo não documentado no código, confirmar com o autor].

### 2. Usar `preco_ativo` como fallback para `preco_compra_ativo`

Rejeitado (ver Decisão #1). O Collar Calendário aceita esse fallback, mas no Colar
Tradicional a ação é comprada no momento — o ask do book é a única fonte confiável.

## Dependências

- `numpy` — `np.log`, `np.sqrt`, `np.exp`
- `scipy.stats.norm` — `norm.cdf`
- `scipy.optimize.brentq` — `calcular_iv`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`

**Não depende de:**
- `calculadora_colar_calendario` (implementações B&S independentes)
- Banco de dados (recebe tudo por parâmetro)
- RTD/OpenFAST

**É dependência de:**
- `src.application.use_cases.monitor_colares.py` → instancia e chama `.calcular()`, `.classificar_tipo()`, `.calcular_risco_leilao()`
- `src.ui.desktop.colar_dialog.py` → importa `ResultadoColar`
- `src.ui.desktop.calculadoras_dialog.py` → usa `black_scholes_call`, `black_scholes_put`, `calcular_iv` como calculadora manual
- `src.ui.desktop.monitor_worker.py` → importa `ResultadoColar`, `TipoColar`

## Cobertura de Teste

**Status: 0 testes.** Nenhum arquivo de teste dedicado existe para este módulo.

O inventory.md (`specs/inventory.md:89`) classifica como "Parcial", mas uma busca exaustiva
(grep por `calculadora_colar` em `tests/`) encontra apenas:
- `test_display_mismatch.py` — importa `ResultadoColar`, `TipoColar`, `RiscoLeilao` para
  testar formatação de display, **não** testa a calculadora em si.

**Lacunas (cobertura zero em todos os métodos):**
- `calcular()` — 0 testes (caminho principal de produção)
- `calcular_iv()` — 0 testes (bracket adaptativo com 20 iterações, múltiplos branches)
- `classificar_tipo()` — 0 testes
- `calcular_risco_leilao()` — 0 testes
- `black_scholes_call()` / `black_scholes_put()` — 0 testes
- `calcular_probabilidade_upside()` / `downside()` — 0 testes
- `calcular_cdi_periodo()` — 0 testes
- Cenários de borda: `custo_liquido ≤ 0`, `preco_compra_ativo ≤ 0`, `cdi_periodo ≤ 0`,
  `iv_call`/`iv_put` não convergindo, leilão com status Aberto vs Fechado, VOV/VOC zerado
