# CalculadoraPutRatio

## Propósito

Calculadora do Put Ratio Spread — estratégia de crédito que compra `n1` PUTs OTM (K1, mais
cara) e vende `n2` PUTs mais OTM (K2, mais barata), com `n2 > n1`. O crédito inicial é
financiado pela venda extra: `credito_bruto = n2 * bid(K2) - n1 * ask(K1)`.

Lucro máximo ocorre se o spot ficar exatamente em K2 no vencimento (PUTs vendidas expiram
OTM, PUT comprada tem valor intrínseco máximo). Abaixo do breakeven `be_down`, a posição
começa a perder (as PUTs vendidas nuas `n2 - n1` criam exposição short ilimitada).

Usa estimativa de IV por Newton-Raphson (não `brentq`) e classifica a qualidade da
proteção em zonas A/B/C baseado na distância do breakeven em sigmas.

## Contrato (Requisitos)

### `calcular(...) -> ResultadoPutRatio | None`

**Garante:**
1. Retorna `None` se: `K1 ≤ K2`, `n2 ≤ n1`, `ask ≤ 0` ou `bid ≤ 0`, `dias ≤ 0`, `credito_bruto ≤ 0`.
2. **Crédito bruto:** `n2 * bid_put_k2 - n1 * ask_put_k1` (R$ total, não por ação).
3. **Lucro máximo:** `n1 * (K1 - K2) + credito_bruto` — ocorre em `S = K2`.
4. **Breakeven baixa:** `be_down = K2 - max_profit / (n2 - n1)`.
5. **Capital/margem:** `(n2 - n1) * K2` (exposição das PUTs nuas).
6. **Rendimento:** `credit_yield = credito_bruto / ((n2 - n1) * K2)`, comparado contra CDI
   via `dc_to_du / 252` (dias úteis).
7. **Proteção (%):** `(spot - be_down) / spot` — quanto o ativo pode cair antes do breakeven.
8. **Sigma BE:** `(spot - be_down) / (spot * iv_mod * sqrt(T))` — distância em desvios-padrão,
   com `T = du/252` (dias úteis, convenção padronizada do sistema para Black-Scholes).
9. **Zona:** A (≥2σ), B (≥1.5σ), C (demais).
10. **Score:** `alpha * protecao_pct + beta * (max_profit/spot) + gamma * (credito/spot)`,
    com pesos configuráveis (`peso_alpha=0.7`, `peso_beta=0.0`, `peso_gamma=0.3` por default).
    Nota: `peso_beta=0.0` zera o termo de max_profit no score padrão.
11. **Profundidade:** exige `qtd_ask_k1 ≥ qtd_min_perna` e `qtd_bid_k2 ≥ qtd_min_perna`.
12. **Viavel:** `credito_bruto > 0` E `lucro_liquido > 0` E profundidade OK.

### `estimar_iv(preco, S, K, T, r) -> float` (static)

**Garante:**
1. Newton-Raphson com 20 iterações, partindo de σ=0.30, intervalo clampado em [0.05, 2.0].
2. Se `preco ≤ intrínseco`, retorna `0.15` (floor, não tenta iterar).
3. Converge quando `|preco_bs - preco_mercado| < 0.0001`.
4. **Não é o mesmo algoritmo que `CalculadoraColar.calcular_iv` ou `CalculadoraColarCalendario.implied_volatility`** — usa Newton-Raphson em vez de `brentq`, tornando-o mais rápido mas potencialmente menos robusto em extremos.
5. **T deve estar em anos na convenção `du/252`** — o chamador (`calcular()`) converte
   de `dias` corridos para `du` via `dc_to_du` e divide por 252. Ver `Decisão #3 (BUG CORRIGIDO)`.

### `delta_put(S, K, T, r, sigma) -> float` (static)

**Garante:**
1. `N(d1) - 1` (delta de PUT, sempre ≤ 0).
2. Retorna `0.0` se `S ≤ 0`, `K ≤ 0`, `T ≤ 0`, ou `sigma ≤ 0`.

## Decisões Tomadas

### 1. Newton-Raphson para IV em vez de `brentq`

**Porquê:** A calculadora processa múltiplos ratios por ativo (3-5 combinações de n1:n2)
e múltiplos pares de strikes. Newton-Raphson é ~5x mais rápido que `brentq` em cenários
típicos e converge em <5 iterações para opções não-extremas. O trade-off é robustez:
`brentq` garante convergência se houver raiz no intervalo; Newton-Raphson pode divergir
se o chute inicial (σ=0.30) estiver longe. [motivo não documentado no código, confirmar com o autor] para a escolha específica de 20 iterações e clamp [0.05, 2.0].

### 2. `peso_beta=0.0` por default

**Porquê:** O termo `max_profit / spot` mede o lucro máximo relativo ao spot — mas `max_profit`
ocorre exatamente em `S = K2`, um ponto único. Dar peso a isso favoreceria operações com
K2 muito próximo de K1 (spread pequeno, baixo risco, baixo retorno). Com peso_beta=0,
o score prioriza proteção (% de queda até o BE) e crédito imediato.

### 3. ~~T = dias / 365 (dias corridos)~~ → BUG CORRIGIDO (07/08/2026): T = du / 252

**Situação original:** A linha 138 usava `T = dias / 365.0` (dias corridos) para o T do
Black-Scholes, baseado na premissa incorreta de que "volatilidade usa dias corridos".
Na prática, o sistema inteiro padronizou `du/252` para Black-Scholes:
`CalculadoraColar` (linha 249), `CalculadoraColarCalendario` (linhas 311-312),
`CalculadoraCaudaAssincrona` (linha 134). O CDI na linha 165 JÁ usava `du/252`
corretamente — o bug era só no T do BS.

**Impacto:** O `T` errado alimentava `estimar_iv` (linha 147-149), `delta_put` (linhas
152-153) e `sigma_be` via `math.sqrt(T)` (linha 178). Para um caso típico (dias=45, du=30,
S=29.50, K=30.0, prêmio=1.00, CDI=14.5%):

| Convenção | T | IV estimada | Delta K1 |
|-----------|---|-------------|----------|
| `dias/365` (antigo) | 0.12329 | 24.16% | -0.4836 |
| `du/252` (corrigido) | 0.11905 | 24.37% | -0.4865 |
| **Divergência** | — | **21bp** | **0.0029** |

**Correção:**
```python
# Antes (bug) — calculadora_put_ratio.py:138:
        T = dias / 365.0

# Depois (corrigido) — calculadora_put_ratio.py:138-139:
        du_val_bs = du if du is not None else dc_to_du(None, None, dias)
        T = du_val_bs / 252.0
```

+2 testes em `TestConvencaoTBlackScholes` cobrindo:
- `test_iv_diverge_entre_convencoes`: prova que `estimar_iv` com `T_dc` vs `T_du` produz
  IV diferente (princípio da divergência).
- `test_calcular_usa_du_252_para_bs`: prova que `calcular()` internamente usa `du/252`
  (delta_k1 mais próximo de `T_du` que de `T_dc`). ANTES do fix: falhava com
  `delta_k1=-0.4836` vs `T_du=-0.4865` (diff=0.0029) mas batia exato com `T_dc` (diff=0.0000).
0 testes existentes quebraram — todos os asserts eram invariantes/relacionais, não de valor exato.
578 testes na suíte, 578 passando.

## Dependências

- `math` — `log`, `sqrt`, `exp`
- `scipy.stats.norm` — `norm.cdf`, `norm.pdf`
- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`

**É dependência de:**
- `src.application.use_cases.monitor_put_ratio.py` → instancia, chama `.calcular()` e `.estimar_iv()`

## Cobertura de Teste

**Status: 50 testes em `tests/domain/test_calculadora_put_ratio.py`**

| Classe | Testes | Cobre |
|---|---|---|
| `TestHappyPath` | 10 | `calcular()` válido, crédito bruto, BE down, capital/margem, sigma_be/zonas, score, viável |
| `TestSigmaBeOrdering` | 3 | sigma_be calculado antes da zona, sigma_be=0 sem IV, zona A |
| `TestRejeicoes` | 10 | guard clauses: K1≤K2, n2≤n1, ask/bid=0, dias≤0, crédito≤0 |
| `TestProfundidade` | 4 | fail-closed: qtd_min=0 ok, qtd_min>0 sem dados rejeita, dados suficientes/insuficientes |
| `TestMultiplosRatios` | 2 | ratio 2x3, 1x3 |
| `TestValoresDerivados` | 5 | lucro líquido, proteção_pct, yield_cdi, delta_k1/k2 negativos |
| `TestSemPrecoAtivo` | 2 | spot=0 ainda retorna, be_down ok sem spot |
| `TestDeltaPut` | 5 | delta_put estático: válido, S=0, K=0, T=0, sigma=0 |
| `TestEstimarIV` | 3 | estimar_iv válida, preço=0, intrinsic only |
| `TestRatiosDefault` | 4 | (1,2), (2,3), (1,3), n2 > n1 |
| `TestConvencaoTBlackScholes` | 2 | **BUG CORRIGIDO:** `estimar_iv` diverge entre `dias/365` e `du/252`; `calcular()` usa `du/252` internamente |

**Lacunas conhecidas (não cobertas):**
- `iv_k1`/`iv_k2` fornecidos externamente (pula `estimar_iv`) — 0 testes
- `du=None` (usa `dc_to_du` internamente) — 0 testes
- `em_leilao=True` com dados reais — 0 testes
- `peso_beta` e `peso_gamma` ≠ default (0.0 e 0.3) — 0 testes
