# CalculadoraColarCalendario

## Propósito

Calculadora central do Collar Calendário — a estratégia que compra ação, vende CALL curta e
compra PUT longa, lucrando com o decaimento temporal diferencial (CALL perde valor mais rápido
nos primeiros `dte_call` dias, enquanto a PUT ainda tem `dte_extra` dias de vida residual).

É a **base de cálculo** para todos os módulos de otimização e proteção: `CalculadoraCaudaAssincrona`
(módulo 3) e `CalculadoraProtecaoCauda` (módulo 2) consomem `ResultadoColarCalendario` como
input direto. Também fornece `black_scholes` estático — a implementação canônica de B&S
usada por todo o sistema (inclusive `calculadora_cauda_assincrona`, que delega B&S para cá).

Além do cálculo financeiro, contém `gerar_explicacao()` — um renderizador HTML completo com
9 cenários de stress, breakevens, análise MOD, custos B3/IR, manejos e integração com proteção
de cauda (BWB / Tail Protect). Este método é chamado pelos dialogs para montar o relatório de
explicação exibido ao usuário.

## Contrato (Requisitos)

### `black_scholes(S, K, T, r, sigma, option_type) -> float` (static)

**Garante:**
1. Implementação canônica de Black-Scholes: `S * N(d1) - K * exp(-rT) * N(d2)` para call,
   `K * exp(-rT) * N(-d2) - S * N(-d1)` para put.
2. Se `sigma ≤ 0` ou `T ≤ 0`, retorna `0.0` (não levanta exceção).
3. `d1 = (ln(S/K) + (r + 0.5*σ²)*T) / (σ*sqrt(T))`, `d2 = d1 - σ*sqrt(T)`.
4. Usa `scipy.stats.norm.cdf` para N(d).

**Fórmulas (grego em valor absoluto, não percentual):**
- `bs_theta()`: retorna theta **diário** (÷ 365 ao final).
- `bs_vega()`: retorna vega em **valor absoluto por 1% de IV** (÷ 100 ao final).
- `bs_gamma()`: retorna `N'(d1) / (S * σ * sqrt(T))`.
- `bs_delta()`: `N(d1)` para call, `N(d1) - 1` para put.

### `implied_volatility(S, K, T, r, market_price, option_type) -> float | None` (static)

**Garante:**
1. Usa `scipy.optimize.brentq` no intervalo `[1e-6, 5.0]` (0.0001% a 500% IV).
2. Se `market_price ≤ 0` ou `T ≤ 0`, retorna `None`.
3. Se `brentq` não convergir (`ValueError` ou `RuntimeError`), retorna `None`.

### `calcular(...) -> ResultadoColarCalendario | None`

**Garante:**
1. Retorna `None` se: `preco_ativo ≤ 0`, `dte_call ≤ 0`, `dte_put ≤ 0`, `premio_call ≤ 0`,
   `premio_put ≤ 0`, ou `qtd_acao/call/put % 100 ≠ 0`.
2. Retorna `None` se `iv_call` ou `iv_put` não convergirem (ex: prêmio abaixo do valor
   intrínseco, `brentq` falha).
3. Retorna `None` se `pnl_projetado ≤ 0`.
4. Retorna `None` se `cdi_periodo ≤ 0`.
5. **Ajuste de dividendos:** se `dividendos` for fornecido, ajusta o spot usado no B&S
   (`S_bs_call`, `S_bs_put`) subtraindo o PV dos dividendos dentro do DTE respectivo.
   Se o spot ajustado ficar `≤ 0`, retorna `None`.
6. **PnL projetado** (modelo coberto, unitário primeiro, depois escala por qtd):
   ```
   pnl_call_unit = premio_call
   pnl_stock_unit = min(preco_ativo, strike_call) - preco_compra
   pnl_put_unit = valor_put_venc_call - premio_put
   pnl_projetado = pnl_call_unit * qtd_call + pnl_stock_unit * qtd_acao + pnl_put_unit * qtd_put
   ```
7. **Capital empregado:** `preco_compra * qtd_acao + premio_put * qtd_put - premio_call * qtd_call`.
   Se capital ≤ 0, usa `abs()` como base para %CDI.
8. **Viabilidade:** `pct_cdi ≥ self.premio_risco`. O parâmetro `premio_risco` é configurado
   externamente (do banco, via `premio_risco_colar_calendario`).
9. **Vencimentos propagados** (desde a criação do módulo, 2026-05-25): `vencimento_call` e `vencimento_put`
   são recebidos como parâmetros e propagados intactos para `ResultadoColarCalendario`.
   O `calculadora_cauda_assincrona.py` inicialmente NÃO carregava esses campos — o filtro de
   vencimento para proteção BWB só foi adicionado em 2026-07-20 (commit `76d5452`).
   O contrato aqui (fornecer os vencimentos) sempre foi cumprido; o bug estava no consumidor.
10. **Classificação por delta:** `|delta_total| ≤ 0.05` → Neutro; `> 0` → Alta; `< 0` → Baixa.
11. **Breakevens:** calcula dois conjuntos — com B&S (considera valor temporal residual da PUT)
    e intrínseco (fallback simplificado: `max(Kp - S, 0)`). Ambos usam `brentq` no intervalo
    `[min(Kp, S0)*(1-be_range_mult), max(Kc, S0)*(1+be_range_mult)]`.

**Parâmetros recebidos (todos por argumento, sem leitura de banco):**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `r` | float \| None | Taxa livre de risco. Se None, usa `self.taxa_cdi` |
| `preco_compra_ativo` | float \| None | Preço de compra real da ação (fallback: `preco_ativo`) |
| `dividendos` | list[tuple[date, float]] \| None | Lista de (data_ex, valor) para ajuste de spot |
| `iv_hist_min`, `iv_hist_max` | float \| None | Histórico para IV Rank |
| `qtd_acao`, `qtd_call`, `qtd_put` | int | Quantidades (múltiplos de 100) |

### `classificar_tipo(preco_ativo, strike_call, strike_put) -> TipoColarCalendario`

**Garante:**
1. Calcula `meio = (Kc + Kp) / 2`, `dist = |preco_ativo - meio|`.
2. Se `dist ≤ (Kc - Kp) * limiar_pct` → NEUTRO.
3. Se `preco_ativo < meio` → ALTA; caso contrário → BAIXA.

### `calcular_preco_ajustado_dividendos(dividendos, preco_ativo, r, dte_max) -> float` (static)

**Garante:**
1. Subtrai do spot o valor presente de dividendos com data-ex dentro de `[hoje+1, hoje+dte_max]`.
2. Desconto: `valor * exp(-r * t)` onde `t = dias_ate_ex / 365`.
3. Ignora dividendos com data-ex passada ou além do `dte_max`.

### `gerar_explicacao(r: ResultadoColarCalendario, taxa_cdi: float) -> str` (static)

**Garante:**
1. Renderiza HTML completo com: título, montagem, 9 cenários de stress (±3σ com drift
   log-normal), breakevens, análise MOD (tipo_opcao da CALL via query no banco), custos
   B3/IR, manejos, integração com proteção de cauda (BWB / Tail Protect).
2. Para cada cenário: PnL da ação + CALL + PUT (com B&S no tempo residual) + naked call.
3. Barras SVG de densidade de probabilidade (pdf normal) para cada cenário.
4. Se `is_otimizado=True`, exibe ratios e explicação da otimização.
5. Se `lado_protegido` não for None/vazio, exibe seção de proteção BWB/Tail.
6. **Resiliência:** usa `getattr()` com defaults para todos os campos opcionais
   (proteção de cauda, ratios, etc.) — não quebra se o `ResultadoColarCalendario` vier
   de uma versão antiga sem esses campos.

## Decisões Tomadas

### 1. Ajuste de dividendos no spot do B&S (não no preço de compra)

**Porquê:** Dividendos reduzem o preço forward da ação. O B&S precisa do spot ajustado
para calcular IV e gregos corretamente. O `preco_compra` (usado no PnL) não é ajustado
porque o PnL real depende do preço que o trader pagou, não do spot teórico.

### 2. IV via `implied_volatility` com `brentq`, não via fórmulas de aproximação

**Porquê:** Fórmulas de aproximação (ex: Corrado-Miller, Let's Be Rational) são mais
rápidas mas menos precisas nos extremos (deep ITM/OTM). `brentq` no intervalo `[1e-6, 5.0]`
é robusto para qualquer combinação de S/K/T/r/preço que apareça no mercado B3. O custo
computacional (~50 avaliações de B&S por convergência) é irrelevante — cada `calcular()`
faz no máximo 2 chamadas de IV.

### 3. Dois conjuntos de breakevens: B&S e intrínseco

**Porquê:** O breakeven B&S considera o valor temporal residual da PUT no vencimento da CALL
(modelo mais realista, mas depende de IV_put convergir). O breakeven intrínseco é um fallback
conservador que não depende de IV — útil para diagnóstico e para cenários onde a PUT está
deep ITM/OTM e o B&S pode divergir. Ambos são calculados e expostos (`be_baixa`, `be_alta`,
`be_baixa_intrinseco`, `be_alta_intrinseco`).

### 4. `bs_theta` retorna theta DIÁRIO (÷ 365), não anual

**Porquê:** Theta diário é a unidade natural para traders — "quantos reais por dia esta
posição perde/g ganha com a passagem do tempo". O B&S padrão retorna theta anual; dividir
por 365 converte para diário. Importante: `dc_to_du / 252` é usado para o CDI e sigma,
mas theta usa 365 (dias corridos, não úteis) porque o decaimento temporal acontece todo
dia, não só em dias de mercado.

### 5. `vega` retorna valor absoluto por 1% de IV (÷ 100)

**Porquê:** O B&S padrão retorna vega por 100% de IV. Dividir por 100 converte para
sensibilidade por 1% — a unidade que traders usam ("se IV subir 1 ponto percentual,
quanto ganho/perco").

### 6. Classificação por delta da estrutura, não por distância de strike

**Porquê:** O `classificar_tipo` baseado em distância de strike (linha 196) é o método
original. Mas dentro de `calcular()`, a classificação real usada no resultado (linha 341)
é por `delta_total` da estrutura (`|delta| ≤ 0.05 → Neutro`). O método `classificar_tipo`
existe mas **não é chamado por `calcular()`** — parece ser um remanescente ou API externa
não utilizada. Confirmar: grep mostra zero chamadas a `classificar_tipo` em `src/`.

### 7. `gerar_explicacao` faz query no banco para MOD da CALL

**Porquê:** A explicação exibida ao usuário inclui análise de risco de exercício antecipado.
Para isso, precisa saber se a CALL é Americana ou Europeia. Como o `ResultadoColarCalendario`
não carrega MOD (regra #2 do AGENTS.md: MOD só da CALL, e só em `importflash.py`), o método
faz uma query direta em `instrumentos_base` via `cod_put` como chave de lookup.
**[motivo não documentado no código, confirmar com o autor]**: por que a query está
aqui (camada de domínio) em vez de o MOD ser passado como parâmetro pelo caller
(`colar_calendario_dialog.py` ou `monitor_colares_calendario.py`), que já tem acesso
ao `InstrumentoRepository` e ao `inst_map`. O fato observável é que este é o único
ponto em toda a camada `src/domain/` que acessa SQL diretamente.

### 8. `vencimento_call`/`vencimento_put` sempre foram propagados

Os campos `vencimento_call` e `vencimento_put` existem no `ResultadoColarCalendario` e são
recebidos como parâmetros de `calcular()` desde a criação do módulo (commit `4a5fa1a`,
2026-05-25). O consumidor downstream (`CalculadoraCaudaAssincrona`) inicialmente não
carregava esses campos — o filtro de vencimento para proteção BWB só foi adicionado em
2026-07-20 (commit `76d5452`). O contrato deste módulo (fornecer os vencimentos) sempre
foi cumprido; o bug estava no consumidor, não aqui.

## Decisões Rejeitadas

### 1. Calcular IV uma vez e cachear por (ativo, strike, vencimento)

Rejeitado porque IV muda a cada ciclo do worker (novo preço de mercado). Cache seria
stale em segundos. O `brentq` é rápido o suficiente para 2 chamadas por par CALL/PUT.

### 2. Usar taxa contínua `log(1+r)` em todo lugar (não só no B&S)

Rejeitado porque o CDI é uma taxa discreta anual. `(1+r)^(du/252) - 1` é a convenção
correta para projetar CDI no período. `log(1+r)` é usado apenas onde B&S exige taxa
contínua (d1, d2, valor presente do strike).

### 3. Breakeven único (só B&S ou só intrínseco)

Rejeitado porque cada um serve a um propósito diferente: B&S para precisão, intrínseco
para diagnóstico e fallback. O custo de calcular ambos é mínimo (2× `brentq`).

### 4. Mover `gerar_explicacao` para a camada de UI

Rejeitado porque o método precisa de `black_scholes`, `dc_to_du`, `np.log`, `norm.cdf`
e lógica de payoff — todas já disponíveis na calculadora. Mover para UI criaria
dependência reversa (UI → domain services) ou duplicação de código.

## Dependências

- `numpy` — `np.log`, `np.sqrt`, `np.exp`
- `scipy.stats.norm` — `norm.cdf`, `norm.pdf`
- `scipy.optimize.brentq` — `implied_volatility`, breakevens
- `src.domain.services.calendario_b3` → `dc_to_du`, `frac_du` (importado mas `frac_du` não usado no arquivo)
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`

**Não depende de:**
- Banco de dados (exceto `gerar_explicacao`, que faz query lazy para MOD)
- RTD/OpenFAST
- `calculadora_cauda_assincrona` ou `calculadora_protecao_cauda`

**Dependências adicionais de `gerar_explicacao()` apenas:**
- `src.infrastructure.persistence.database` → `get_connection` (query MOD da CALL)

**É dependência de:**
- `src.application.use_cases.monitor_colares_calendario.py` → instancia e chama `.calcular()`
- `src.domain.services.calculadora_cauda_assincrona.py` → `black_scholes`, `ResultadoColarCalendario`
- `src.domain.services.calculadora_protecao_cauda.py` → `ResultadoColarCalendario`
- `src.ui.desktop.colar_calendario_dialog.py` → importa `ResultadoColarCalendario`, chama `CalcularColarCalendario` em calculadora manual
- `src.ui.desktop.monitor_worker.py` → importa `ResultadoColarCalendario`, `TipoColarCalendario`
- `src.ui.desktop.estudos_calendario_dialog.py` → importa `CalculadoraColarCalendario`

## Cobertura de Teste

**Status: 57 testes em `tests/domain/test_calculadora_colar_calendario.py`** (13 classes)

| Classe | Testes | Cobre |
|---|---|---|
| `TestBlackScholes` | 7 | `black_scholes`: call ATM, put ATM, call ITM, call OTM, sigma=0, T=0, call-put parity |
| `TestBsTheta` | 4 | `bs_theta`: call negativo, put negativo, sigma=0, T=0 |
| `TestImpliedVolatility` | 4 | `implied_volatility`: preço conhecido, preço=0, T=0, OTM call |
| `TestCalcularCdiPeriodo` | 4 | `calcular_cdi_periodo`: 1 ano B3, zero dias, negativo, meio ano |
| `TestClassificarTipo` | 5 | `classificar_tipo`: alta, baixa, neutro, fronteira, spread zero |
| `TestCalcular` | 6 | `calcular()`: happy path, preco_ativo=0, premio=0, dte=0, pnl negativo → None, viabilidade por premio_risco |
| `TestCalcularPvDividendos` | 8 | `calcular_preco_ajustado_dividendos` + integração com `calcular()`: sem dividendos, futuro reduz preço, passado ignorado, fora DTE ignorado, múltiplos, r=0, com dividendos calcular retorna resultado |
| `TestGerarExplicacao` | 1 (parametrized é 1) | `gerar_explicacao`: gera HTML |
| `TestVega` | 5 | `bs_vega`: call positivo, put positivo, put > call, sigma=0, T=0 |
| `TestGamma` | 3 | `bs_gamma`: positivo, sigma=0, T=0 |
| `TestRiscoMax` | 2 | risco_max: zero para risk-free, positivo com risco |
| `TestIvRank` | 3 | IV Rank: sem histórico, com histórico, histórico inválido |
| `TestQtdMultiplo100` | 5 | qtd % 100 ≠ 0 rejeitada (ação, call, put), múltiplo de 100 aceito, múltiplo de 300 aceito, `gerar_explicacao` snap ratio_call para lote |

**Lacunas conhecidas (não cobertas):**
- `classificar_tipo()` como API pública — 0 chamadas em produção, testado apenas unitariamente
- `frac_du` importado de `calendario_b3` mas nunca usado no arquivo (import morto)
- `_pnl_at_call_expiry` — testado indiretamente via breakevens, sem teste unitário direto
- `gerar_explicacao` com `is_otimizado=True` + proteção BWB ativa — caminho complexo não testado
- `gerar_explicacao` com `mod_call=None` (falha na query do banco) — cenário de erro não testado
- `calcular()` com dividendos que zeram o spot ajustado (`S_bs_call ≤ 0`) — branch não testado
- `risco_max` com `capital_empregado > 0` e `min(Kc, Kp) * qtd_acao > capital` — fórmula complexa,
  testada superficialmente
- Interação entre `preco_compra_ativo` explícito e `divendos` no mesmo `calcular()` — não testado
