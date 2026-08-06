# CalculadoraCaudaAssincrona

## Propósito

Pós-processa um `ResultadoColarCalendario` viável e encontra o par `(ratio_call, ratio_put)`
— ambos em float — que maximiza o %CDI mantendo PnL > 0 nos extremos de ±Nσ no vencimento
da call. É o motor de otimização de ratio que transforma Collar Calendário neutro (ratio 1:1)
em operações com exposição naked controlada (call ratio > 1.0 e/ou put ratio < 1.0),
aumentando o retorno via venda adicional de calls ou redução de hedge de puts.

Duas entradas:
- **`calcular()`** — busca binária: encontra o melhor par único que atinge ≥ `calda_premio_risco × CDI`,
  retornando `ResultadoCaudaAssincrona | None`.
- **`processar_otimizado()`** — varre o grid completo, retornando lista com até 2 variantes
  (`estagio="Base"` com ratio 1:1, e `estagio="Otimizado"` com o melhor par que passa
  no filtro de Rendimento a ±2σ). Usado pelo `MonitorWorker` para alimentar a proteção de cauda.

## Contrato (Requisitos)

### `calcular()` — otimização com target de %CDI

**Garante:**
1. Retorna `None` se: `iv_call_pct ≤ 0`, `dte_call ≤ 0`, `preco_ativo ≤ 0`, ou `cdi_periodo ≤ 0`.
2. Retorna `None` se nenhum par `(n, m)` atingir o piso de PnL.
3. Se `gap ≤ 0` (PnL base já atinge ≥ target), só varre `n = 1.0` (não vende calls extras).
4. Todo par `(n, m)` passado pelo filtro tem `pnl_spot > 0` e `pnl_spot + delta_l, pnl_spot + delta_r ≥ CDI × capital`.
5. O melhor par é escolhido por `max(pct_cdi)`.
6. **Snap para lote B3**: após escolha, ratios são arredondados para múltiplos de 100 ações
   (`n_snap = round(n × qtd_acao / 100) × 100 / qtd_acao`), PnL e extremos recalculados.
7. Se o PnL pós-snap for ≤ 0, retorna `None`.
8. Retorna `ResultadoCaudaAssincrona` com `viavel=True`, `range_ok=True`, breakevens, sigma, k_3sigma.

**Fórmula crítica — pnl_spot (BUG HISTÓRICO CORRIGIDO):**

```
pnl_spot = pnl_projetado_base
         + (n - 1) × extra_call_pnl × qtd_acao    ── termo INCREMENTAL da call
         + (1 - m) × custo_put × qtd_acao         ── termo INCREMENTAL da put
```

⚠️ **BUG HISTÓRICO:** a versão original omitia a multiplicação por `qtd_acao` nos termos incrementais,
fazendo o termo entrar ~1000× menor que o correto (confundindo valor "por ação" com valor "de portfólio inteiro").
Isso mascarava quase todo o efeito da otimização de ratio. Este contrato existe especificamente
para que essa fórmula **nunca regrida** numa refatoração futura.

**Fórmula — delta_pnl:**
```
delta_pnl(S, S_ref, Kc, Kp, n, m) = (S - S_ref)
  - n × (max(0, S - Kc) - max(0, S_ref - Kc))     ── call payoff (intrínseco, expirou)
  + m × (bs_put_S - bs_put_ref)                    ── put payoff (B&S tempo residual)
```
`delta_pnl` retorna valor **por ação**; o chamador multiplica por `qtd_acao`.

**Fórmula — breakeven_esquerdo (S < Kp):**
```
be_esq = (S0_cost - n × Pc - m × (Kp - Pp)) / (1 - m)
```
Retorna `None` se `m ≥ 1.0` ou denominador ≤ 0.

**Fórmula — breakeven_direito (S > Kc):**
```
be_dir = (n × (Kc + Pc) - S0_cost - m × Pp) / (n - 1)
```
Retorna `None` se `n ≤ 1` ou denominador ≤ 0.

**Parâmetros de negócio (todos recebidos por argumento):**

| Parâmetro | Default | Unidade | Descrição |
|---|---|---|---|
| `calda_premio_risco` | 2.5 | múltiplo | CDI mínimo para aceitar otimização |
| `calda_desvios_cauda` | 3.0 | σ | Nº de sigmas para teste de extremos |
| `calda_ratio_max` | 50 | % | Call ratio máximo = 1.0 + calda_ratio_max/100 |
| `calda_ratio_put_min` | 0.3 | fração | Put ratio mínimo (0.3 = 30% do hedge base) |
| `calda_ratio_put_step` | 0.1 | fração | Passo do grid de busca |
| `calda_capital_minimo_pct` | 0.0 | fração | Reserva de capital (não implementado no grid, parâmetro recebido mas ignorado) |
| `taxa_cdi` | 0.1450 | decimal | Taxa CDI anual |
| `qtd_acao` | 100 | ações | Quantidade base de ações |
| `preco_compra` | None | R$/ação | Preço de compra para breakeven (fallback: `preco_ativo`) |

### `processar_otimizado()` — varredura multi-variante

**Garante:**
1. Retorna `[]` se `iv ≤ 0`, `dte_call ≤ 0`, `preco_ativo ≤ 0`, `cdi_periodo ≤ 0`, ou `capital ≤ 0`.
2. Retorna `[]` se nenhum par `(n, m)` tiver PnL ≥ 0 nos extremos.
3. Varre todos os pares `(n, m)` no grid. Não tem o corte `gap ≤ 0` do `calcular()`.
4. Filtro de extremos: `pnl ≥ 0` a ±`otimizado_desvios_sigma` (default 3σ).
5. Filtro "Rendimento": dos que passam no item 4, seleciona os que têm `pnl ≥ CDI × capital` a ±`otimizado_sigma_rendimento` (default 2σ).
6. Sempre inclui `estagio="Base"` com `n=1.0, m=1.0` se este par estiver nos candidatos.
7. Inclui `estagio="Otimizado"` com o melhor %CDI dentre os que passam no filtro de Rendimento.
8. Todos os ratios são snapped para lote B3.
9. Se o snap zerar o PnL de uma variante, ela é omitida.
10. Todas as variantes compartilham o mesmo `id_chassi` (UUID de 8 chars).

**Parâmetros específicos do `processar_otimizado()`:**

| Parâmetro | Default | Unidade | Descrição |
|---|---|---|---|
| `otimizado_ratio_put_min` | 0.80 | fração | Put ratio mínimo (mais conservador que `calcular`) |
| `otimizado_ratio_max` | 1.30 | múltiplo | Call ratio máximo (mais conservador que `calcular`) |
| `otimizado_desvios_sigma` | 2.0 | σ | Sigma para veto de PnL < 0 |
| `otimizado_sigma_rendimento` | 2.0 | σ | Sigma para filtro de CDI (Rendimento) |
| `otimizado_ratio_put_step` | 0.10 | fração | Passo do grid |

**Unidades e convenções:**

- `pnl_projetado_base` e `pnl_spot` = valor total do portfólio (R$). Já inclui escala de `qtd_acao`.
- `extra_call_pnl` e `custo_put` = valor **por ação** (R$/ação). Multiplicados por `qtd_acao` nos termos incrementais.
- `delta_pnl` = valor **por ação**, multiplicado por `qtd_acao` no call site.
- `capital_empregado_base` = R$ total. Usa-se `abs()` se negativo (capital_empregado negativo = operação travada, mas %CDI usa módulo).
- `iv_call_pct` = porcentagem (ex: 25.5 = 25.5%). Convertido para decimal via `/ 100.0`.
- `premio_call`, `premio_put` = R$/ação. Intrínseco da call: `max(0, preco_ativo - strike_call)`.

## Decisões Tomadas

### 1. Grid de busca em float, não otimização contínua

**Porquê:** Ratios são discretos na prática (lote B3 = 100 ações). Um grid com step configurável
(`calda_ratio_put_step`) cobre todos os pares viáveis sem custo computacional relevante
(n_vals × m_vals ≤ ~50 × ~10 = 500 iterações). Tentar `scipy.optimize` seria overkill
e potencialmente instável com a função não-diferenciável do payoff.

### 2. B&S para PUT com tempo residual, intrínseco para CALL (expirada)

**Porquê:** O cenário de cauda é avaliado no vencimento da CALL, quando a CALL já expirou
(payoff = intrínseco), mas a PUT ainda tem `dte_extra = dte_put - dte_call` dias restantes.
Se `iv_put` estiver disponível e `dte_extra > 0`, usa B&S para precificar a PUT no spot extremo.
Caso contrário, fallback para valor intrínseco da PUT — menos preciso, mas seguro
(conservador — superestima o payoff da PUT, penalizando o PnL na cauda).

### 3. `processar_otimizado` usa limites mais conservadores que `calcular`

**Porquê:** `calcular()` é a otimização livre — explora ratios extremos (até 1.50 call, até 0.30 put)
buscando maximizar %CDI. `processar_otimizado()` alimenta a proteção de cauda e deve ser
mais contido (call ≤ 1.30, put ≥ 0.80) porque:
- Ratio call muito alto → grande exposição naked → custo de proteção proibitivo.
- Ratio put muito baixo → pouco hedge → breakeven esquerdo explode.
Os defaults mais conservadores no worker (`otimizado_*`) refletem essa intenção.

### 4. Breakeven usa `preco_compra` (não `preco_ativo`)

**Porquê:** O breakeven é o preço onde a operação fecha em zero **para o trader**,
que pagou `preco_compra` pela ação. Se `preco_compra` não for informado, fallback para
`preco_ativo`. O `delta_pnl`, por outro lado, usa `preco_ativo` como referência porque
mede a variação de PnL do ponto atual para o extremo.

### 5. `gap ≤ 0` bloqueia venda extra de calls em `calcular()`

**Porquê:** Se o PnL base já atinge ≥ `calda_premio_risco × CDI`, vender mais calls
(n > 1.0) só aumentaria o risco de cauda sem necessidade — o CDI já está no target.
O `processar_otimizado()` não tem esse corte porque seu propósito é justamente
gerar as variantes para a proteção de cauda, mesmo quando a base já é suficiente.

### 6. `calda_capital_minimo_pct` é recebido mas ignorado

**Porquê:** [motivo não documentado no código, confirmar com o autor]. O parâmetro está
na assinatura e é passado pelo worker (`monitor_worker.py`), mas não é consumido
em nenhum branch do grid de busca. Pode ser resquício de uma feature planejada
de reserva de capital que nunca foi implementada, ou pode ter sido removida
sem limpeza da assinatura.

### 7. `custo_b3_base` e `custo_protecao` não são recalculados no `calcular()`

**Porquê:** O custo B3 é calculado externamente (no use case) e recebido como parâmetro.
O módulo não tem dependência de `CalculadoraCustosB3`. Se os ratios mudarem,
o custo B3 deveria tecnicamente ser recalculado — mas a diferença é marginal
(emolumentos + liquidação são ~0.06% do financeiro) e ignorada por simplicidade.

### 8. BUG HISTÓRICO CORRIGIDO (07/08/2026): `bs_put_ref = 0.0` no `calcular()` sem BS

**Situação original:** O else de `calcular()` (linha ~160) usava `bs_put_ref = bs_end_l = bs_end_r = 0.0`
quando `usar_bs=False`, enquanto `processar_otimizado()` (linha ~342) sempre usou
`max(0, strike_put - S)` como fallback intrínseco. Isso fazia `calcular()` ignorar
completamente o payoff intrínseco da PUT nos extremos de cauda quando não havia
dados de IV para a PUT.

**Impacto:** Com PUT ITM (`strike_put > preco_ativo`), o `pnl_na_cauda_esquerda`
era subestimado — o delta_pnl continha apenas o movimento da ação e da call,
sem a proteção da PUT. Teste `TestPutIntrinsecoSemBS` criado ANTES do fix
provou a divergência: `pnl_na_cauda_esquerda = 323.33` vs esperado `1572.75`
(com `bs_put_ref_intr = 1.0`, `bs_end_l_intr = 5.17` para `strike_put=26.0 > spot=25.0`).

**Correção:** Alinhado o else de `calcular()` com `processar_otimizado()`:
```python
# Antes (bug):
else:
    bs_put_ref = bs_end_l = bs_end_r = 0.0
    custo_put = premio_put - max(0, strike_put - preco_ativo)

# Depois (corrigido):
else:
    bs_put_ref = max(0, strike_put - preco_ativo)
    bs_end_l = max(0, strike_put - s_end_l)
    bs_end_r = max(0, strike_put - s_end_r)
    custo_put = premio_put - bs_put_ref
```
`custo_put` é idêntico nos dois casos (ambos usam `max(0, Kp - S)`).
0 testes existentes quebraram — todos os cenários de teste usavam PUT OTM,
onde o intrínseco é zero e o bug não se manifestava.
+1 teste em `TestPutIntrinsecoSemBS` cobrindo PUT ITM sem BS.
582 testes na suíte, 582 passando.


## Decisões Rejeitadas

### 1. Otimização via `scipy.optimize.minimize` com gradiente
Rejeitada porque o payoff de opções é não-diferenciável nos strikes, e o grid
de busca é pequeno o suficiente (~500 pares) para ser exaustivo em < 1ms.

### 2. Usar o mesmo método para `calcular()` e `processar_otimizado()`
Rejeitada porque os critérios de filtro são diferentes:
- `calcular()`: target de CDI, veto por CDI nos extremos.
- `processar_otimizado()`: veto por PnL < 0 nos extremos, filtro de Rendimento a 2σ.
Unificar forçaria condicionais demais num método só, piorando legibilidade.

### 3. Não snapar para lote B3 (manter ratios float exatos)
Rejeitada porque na prática a operação é executada em múltiplos de 100 ações.
Um ratio de 1.23 com `qtd_acao=1000` geraria 12.3 contratos — impossível de executar.
O snap garante que os resultados do otimizador são executáveis.

### 4. Recalcular custo B3 com os novos ratios
Rejeitada por simplicidade — a diferença é desprezível (~0.06% do financeiro)
e adicionaria dependência de `CalculadoraCustosB3` ao módulo.

## Dependências

- `math` — `sqrt`, `log`
- `uuid` — `uuid4()` para `id_chassi` (apenas `processar_otimizado`)
- `dataclasses` — `ResultadoCaudaAssincrona`
- `src.domain.services.calendario_b3` → `dc_to_du` (dias corridos → dias úteis)
- `src.domain.services.calculadora_colar_calendario` → `CalculadoraColarCalendario.black_scholes` (precificação PUT com tempo residual)

**Não depende de:**
- Banco de dados (recebe tudo por parâmetro)
- RTD/OpenFAST
- `calculadora_custos_b3`
- `numpy` / `scipy` (B&S é delegado para `CalculadoraColarCalendario`)

**É dependência de:**
- `src.domain.services.calculadora_protecao_cauda.py` → `ResultadoCaudaAssincrona`
- `src.ui.desktop.monitor_worker.py` → `CalculadoraCaudaAssincrona`, `ResultadoCaudaAssincrona`

## Cobertura de Teste

**Status: 46 testes em `tests/domain/test_calculadora_cauda_assincrona.py`** (6 classes)

| Classe | Testes | Cobre |
|---|---|---|
| `TestCaudaBasics` | 13 | `calcular()`: ratio_call float, ratio_put entre min e 1, range_ok, breakevens, retorno None (iv=0, dte=0), gap grande → n>1, be_dir p/ ratio=1 e ratio=2, be_dir converge, be_esq, pnl positivo, score positivo |
| `TestProcessarOtimizado` | 11 | `processar_otimizado()`: retorna lista, ≤4 variantes, mesmo id_chassi, estágios Base+Otimizado, ratios no range, PnL cauda veto 3σ, retorna vazio (iv=0, dte=0), breakevens, campos preenchidos |
| `TestLoteB3` | 6 | Snap B3: ratio_call→contratos inteiros, ratio_put→contratos inteiros, snap para inteiro, lote 200, processar_otimizado snaps, calcular retorna None se snap zera PnL |
| `TestSigmaConsistencia` | 4 | sigma usa `dc_to_du`, `processar_otimizado` sigma usa `dc_to_du`, DU aproximado consistente com 365, sigma concorda entre `calcular` e `processar_otimizado` |
| `TestPutIntrinsecoSemBS` | 1 | **BUG CORRIGIDO:** PUT ITM sem BS → `pnl_na_cauda_esquerda` reflete proteção intrínseca (prova que `bs_put_ref > 0` no fallback) |
| `TestVencimentoPropagation` | 2 | `processar_otimizado` propaga vencimentos diferentes, sem vencimento não quebra |

**Lacunas conhecidas (não cobertas):**
- `preco_compra` explícito (≠ preco_ativo) no breakeven — 0 testes
- `calda_capital_minimo_pct` — parâmetro fantasma, sem teste de regressão
- Grid com step < 0.10 (ex: `calda_ratio_put_step = 0.05`)
- `usar_bs = True` com PUT no dinheiro (`iv_put > 0` e `dte_extra > 0`, strike_put > preco_ativo)
- `calcular()` com `gap ≤ 0` (só testa n=1.0)
- `processar_otimizado()` com `capital_empregado_base < 0` (usa abs)
- `cdi_periodo ≤ 0` em ambos os métodos
- Cenário com B&S ativo (`iv_put > 0` e `dte_extra > 0`) nos testes de integração
