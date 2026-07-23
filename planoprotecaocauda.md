# Plano de Integração — Proteção de Cauda (BWB)

**Módulo isolado:** `src/domain/services/calculadora_protecao_cauda.py` — pronto, 183 linhas, 31 testes passando.  
**Pré-requisito:** `calculadora_cauda_assincrona.py` já no pipeline com fix de escala (commit `47ab56d`).

---

## Visão geral: o que a calculadora precisa

`avaliar()` consome 8 campos do chassi (`ResultadoCaudaAssincrona`):

| Campo | Usado para |
|---|---|
| `ratio_call` / `ratio_put` | Calcular `naked_call_frac` e `naked_put_gap` |
| `pnl_com_ratio` / `pnl_base` | Calcular `ganho_extra_ratio` (limite de custo) |
| `preco_ativo` / `sigma_periodo` | Calcular `s_target_call` e `s_target_put` |
| `id_chassi` / `ativo` | Preencher resultado de saída |

E recebe `strikes_call_candidatos` / `strikes_put_candidatos` como lista de dicts:

```python
{"strike": float, "premio_ask": float, "cab": int}
```

**Retorna `None`** quando `naked_call_frac < 2%` E `naked_put_gap < 2%` (~60% dos chassis).

---

## 1. Parâmetros no banco (5 arquivos)

### 1.1. `config/parametros_default.json`

Adicionar ao array `parametros`:

```json
{"chave": "limite_protecao_pct", "valor": "0.35", "estrategia": "PROTECAO_CAUDA", "descricao": "Fracao maxima do ganho extra consumida pela protecao de cauda"},
{"chave": "calda_preco_min_opcao", "valor": "0.01", "estrategia": "PROTECAO_CAUDA", "descricao": "Preco minimo (R$) da opcao de protecao"},
{"chave": "cab_minimo_protecao", "valor": "1", "estrategia": "PROTECAO_CAUDA", "descricao": "CAB minimo para strike candidato (RTD) / VOL_ASK minimo (OpenFast)"},
{"chave": "n_sigma_protecao", "valor": "2.0", "estrategia": "PROTECAO_CAUDA", "descricao": "Numero de sigmas para definir s_target da cauda"}
```

### 1.2. `src/domain/entities/parametro_operacional.py`

Adicionar ao `PARAMETROS_DEFAULT` (linha 19+):

```python
"limite_protecao_pct": {"valor": 0.35, "estrategia": "PROTECAO_CAUDA", "descricao": "Fração máx do ganho extra consumida pela proteção"},
"calda_preco_min_opcao": {"valor": 0.01, "estrategia": "PROTECAO_CAUDA", "descricao": "Preço mínimo (R$) da opção de proteção"},
"cab_minimo_protecao": {"valor": 1, "estrategia": "PROTECAO_CAUDA", "descricao": "CAB mínimo / VOL_ASK mínimo"},
"n_sigma_protecao": {"valor": 2.0, "estrategia": "PROTECAO_CAUDA", "descricao": "Nº de sigmas para s_target da cauda"},
```

### 1.3. `src/ui/desktop/parametros_widget.py`

**`_SIDEBAR_ORDER`** (linha 719): inserir `"PROTECAO_CAUDA"` após `"RATIOS_OTIMIZADOS"` e antes de `"BOX"`:

```python
_SIDEBAR_ORDER = [
    "GERAL",
    "COLAR",
    "COLLAR_CALENDARIO",
    "RATIOS_OTIMIZADOS",
    "PROTECAO_CAUDA",      # <-- novo
    "BOX",
    ...
]
```

**`ESTRATEGIA_LABELS`** (buscar dict no arquivo): adicionar `"PROTECAO_CAUDA": "Proteção de Cauda (BWB)"`.

**`ESTRATEGIA_COLORS`** (buscar dict no arquivo): adicionar `"PROTECAO_CAUDA": Palette.ACCENT_WARNING` ou cor similar.

**`PARAMETROS_POR_ESTRATEGIA`** (linha 60+): adicionar seção:

```python
"PROTECAO_CAUDA": [
    ("limite_protecao_pct", "Limite de Custo (% do ganho extra)"),
    ("calda_preco_min_opcao", "Preço Mínimo da Opção (R$)"),
    ("cab_minimo_protecao", "CAB / Vol.Ask Mínimo"),
    ("n_sigma_protecao", "Nº de Sigmas (s_target)"),
],
```

**`PARAMETROS_INFO`** (linha 231+): adicionar tooltips:

```python
"limite_protecao_pct": {
    "descricao": "Fração máxima do ganho extra (pnl_com_ratio − pnl_base) que a proteção de cauda pode consumir. Ex: 0.35 = até 35% do ganho extra.",
    "usado_em": "CalculadoraProtecaoCauda — filtro de viabilidade da proteção",
},
"calda_preco_min_opcao": {
    "descricao": "Preço mínimo (ask, em R$) para uma opção de proteção ser considerada. Filtra opções sem liquidez real.",
    "usado_em": "CalculadoraProtecaoCauda — filtro de strikes candidatos",
},
"cab_minimo_protecao": {
    "descricao": "CAB mínimo do book (Profit RTD) ou VOL_ASK mínimo (OpenFast) para considerar o strike. Garante profundidade de mercado.",
    "usado_em": "CalculadoraProtecaoCauda — filtro de strikes candidatos",
},
"n_sigma_protecao": {
    "descricao": "Número de desvios-padrão para definir o strike-alvo da proteção. s_target = preco_ativo × (1 ± n_sigma × sigma_periodo).",
    "usado_em": "CalculadoraProtecaoCauda — cálculo de s_target",
},
```

**`_build_param_row`** (linha 877+): os 4 parâmetros são `float`, o `NoWheelSpinBox` padrão serve. Ajustar ranges:
- `limite_protecao_pct`: range 0.01–0.99, step 0.01, suffix `""` (exibido como fração, multiplicar por 100 no label)
- `calda_preco_min_opcao`: range 0.00–1.00, step 0.01, prefix `"R$ "`
- `cab_minimo_protecao`: range 0–100, step 1, int (usar `QSpinBox`)
- `n_sigma_protecao`: range 0.5–5.0, step 0.1

### 1.4. `src/infrastructure/persistence/database.py`

No `_seed_parametros_colar()` ou seção equivalente, a lista `param_default` já cobre via `PARAMETROS_DEFAULT` + JSON. Verificar se a seed de `PROTECAO_CAUDA` é coberta — o fluxo padrão é `JSON → INSERT OR IGNORE → ParametroOperacional.defaults()`, então basta garantir que o JSON tem as entradas (passo 1.1).

---

## 2. Captura RTD expandida para strikes OTM

**Arquivo:** `src/ui/desktop/monitor_worker.py`

### 2.1. Novo método auxiliar: `_resolver_strikes_protecao()`

Criar método no `MonitorWorker` que, para cada chassi, consulta `instrumentos_opcionais` e registra strikes no provider:

```python
def _resolver_strikes_protecao(self, resultado, n_sigma, cab_minimo):
    """Retorna (strikes_call_candidatos, strikes_put_candidatos) para um chassi."""
    s_target_call = resultado.preco_ativo * (1.0 + n_sigma * resultado.sigma_periodo)
    s_target_put = resultado.preco_ativo * (1.0 - n_sigma * resultado.sigma_periodo)

    # ── consultar instrumentos_opcionais ──
    # SELECT ativo, cod_opcao, strike, tipo, vencimento, dte
    # FROM instrumentos_opcionais
    # WHERE ativo = ? AND tipo = 'CALL' AND strike >= ? ORDER BY strike LIMIT 5
    # WHERE ativo = ? AND tipo = 'PUT' AND strike <= ? ORDER BY strike DESC LIMIT 5

    # ── registrar códigos no RTD ──
    campos = [FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.VOL_ASK,
              FieldName.BOOK_HEADER]  # BOOK_HEADER só funciona no Profit RTD
    for cod in codigos_call + codigos_put:
        self.source.registrar(cod, campos)

    # ── montar dicts (após self.source.refresh() no ciclo) ──
    # Ler do cache: self._mercado_provider.ler_campos(cod, campos)
    # Montar dict: {"strike": ..., "premio_ask": of_venda (ASK), "cab": CAB}
    # CAB = 0 quando fonte for openfast
```

### 2.2. Alternativa CAB para OpenFast

`BOOK_HEADER` (`"CAB"`) não existe no OpenFast (só Profit RTD). Para OpenFast, usar `VOL_ASK` como proxy de qualidade:

```python
fonte = self._ler_param_str("fonte_market_data", "profit")
if fonte == "openfast":
    cab_proxy = vol_ask  # usa volume ask em vez de CAB
else:
    cab_proxy = cab
```

O parâmetro `cab_minimo_protecao` é checado contra `cab_proxy` (RTD usa CAB real, OpenFast usa `VOL_ASK`).

### 2.3. Otimização: cache de strikes por ativo

Para evitar query no banco a cada ciclo (24 chassis × 5 strikes = 120 queries), cache em dict:

```python
self._cache_strikes_protecao: dict[str, tuple] = {}  # chave: ativo, valor: (calls, puts, vencimento)
```

Limpar no `recarregar_parametros()` e a cada N ciclos (ex: 10).

---

## 3. Integrar chamada no pipeline

**Arquivo:** `src/ui/desktop/monitor_worker.py`, método `_processar_otimizado()`

### 3.1. Ponto de inserção

Dentro do `for v in variantes:` (linha 602), **após** o filtro de estágio/CDI (linha 603-604) e **antes** da montagem dos ratios (linha 605):

```python
# linha 603-604: filtro existente
if v.estagio != "Base" and v.pct_cdi_com_ratio < max(r.pct_cdi, premio_risco):
    continue

# ─── NOVO: avaliar proteção de cauda ───
candidatos_call, candidatos_put = self._resolver_strikes_protecao(
    v, n_sigma_protecao, cab_minimo_protecao
)
protecao = CalculadoraProtecaoCauda.avaliar(
    resultado=v,
    strikes_call_candidatos=candidatos_call,
    strikes_put_candidatos=candidatos_put,
    qtd_acao=r.qtd_acao,
    n_sigma=n_sigma_protecao,
    limite_protecao_pct=limite_protecao_pct,
    calda_preco_min_opcao=calda_preco_min_opcao,
    cab_minimo=cab_minimo_protecao,
)

n = v.ratio_call       # linha 605 existente
m = v.ratio_put        # linha 606 existente
```

### 3.2. Tratar retorno `None`

`avaliar()` retorna `None` quando exposição naked é insignificante. Os campos no dict devem ser padronizados:

```python
if protecao is None:
    protecao_campos = {
        "lado_protegido": "nenhum",
        "naked_call_frac": 0.0,
        "naked_put_gap": 0.0,
        "strike_protecao_call": None,
        "strike_protecao_put": None,
        "premio_ask_call": None,
        "premio_ask_put": None,
        "qtd_protecao_call": 0,
        "qtd_protecao_put": 0,
        "custo_protecao_call": 0.0,
        "custo_protecao_put": 0.0,
        "custo_protecao_total": 0.0,
        "pnl_liquido_pos_protecao": v.pnl_com_ratio,
        "viavel": 0,
    }
else:
    protecao_campos = {
        "lado_protegido": protecao.lado_protegido,
        "naked_call_frac": protecao.naked_call_frac,
        "naked_put_gap": protecao.naked_put_gap,
        "strike_protecao_call": protecao.strike_protecao_call,
        "strike_protecao_put": protecao.strike_protecao_put,
        "premio_ask_call": protecao.premio_ask_call,
        "premio_ask_put": protecao.premio_ask_put,
        "qtd_protecao_call": protecao.qtd_protecao_call,
        "qtd_protecao_put": protecao.qtd_protecao_put,
        "custo_protecao_call": protecao.custo_protecao_call,
        "custo_protecao_put": protecao.custo_protecao_put,
        "custo_protecao_total": protecao.custo_protecao_total,
        "pnl_liquido_pos_protecao": protecao.pnl_liquido_pos_protecao,
        "viavel": 1 if protecao.viavel else 0,
    }
```

### 3.3. Acrescentar `protecao_campos` ao dict `registros`

No `registros.append({...})` (linha 613+), fazer merge com `**protecao_campos`:

```python
registros.append({
    "id_chassi": v.id_chassi,
    ...
    "tipo_estrategia": tipo_estrategia,
    **protecao_campos,   # <-- novo
})
```

---

## 4. Expandir banco: `historico_simulacoes` + `salvar_lote`

### 4.1. Migração: `database.py` → `_migrar_historico_simulacoes()`

Adicionar 14 tuplas à lista `novas_colunas` (linha 115+):

```python
# Proteção de Cauda (BWB) — ~linha 145
("lado_protegido", "TEXT"),
("naked_call_frac", "REAL"),
("naked_put_gap", "REAL"),
("strike_protecao_call", "REAL"),
("strike_protecao_put", "REAL"),
("premio_ask_call", "REAL"),
("premio_ask_put", "REAL"),
("qtd_protecao_call", "INTEGER"),
("qtd_protecao_put", "INTEGER"),
("custo_protecao_call", "REAL"),
("custo_protecao_put", "REAL"),
("custo_protecao_total", "REAL"),
("pnl_liquido_pos_protecao", "REAL"),
("viavel", "INTEGER"),
```

Padrão: `ALTER TABLE historico_simulacoes ADD COLUMN {col} {tipo}` com `try/except` — já existente (linhas 146-150).

### 4.2. INSERT: `repositories.py` → `HistoricoSimulacoesRepository.salvar_lote()`

Adicionar as 14 colunas em 3 lugares:

**a) Lista de colunas** (linha 998+): acrescentar ao final da string SQL:

```python
, lado_protegido, naked_call_frac, naked_put_gap,
  strike_protecao_call, strike_protecao_put,
  premio_ask_call, premio_ask_put,
  qtd_protecao_call, qtd_protecao_put,
  custo_protecao_call, custo_protecao_put,
  custo_protecao_total, pnl_liquido_pos_protecao, viavel
```

**b) Placeholders** (linha 1011+): acrescentar 14 `?`:

```python
?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
```

**c) Extração do dict** (linha 1021+): acrescentar:

```python
r.get("lado_protegido"), r.get("naked_call_frac"), r.get("naked_put_gap"),
r.get("strike_protecao_call"), r.get("strike_protecao_put"),
r.get("premio_ask_call"), r.get("premio_ask_put"),
r.get("qtd_protecao_call", 0), r.get("qtd_protecao_put", 0),
r.get("custo_protecao_call", 0.0), r.get("custo_protecao_put", 0.0),
r.get("custo_protecao_total", 0.0), r.get("pnl_liquido_pos_protecao", 0.0),
r.get("viavel", 0),
```

**Atenção:** manter a ordem das colunas, placeholders e valores sincronizada.

---

## 5. Arquivos tocados — resumo

| # | Arquivo | Mudança |
|---|---|---|
| 1 | `config/parametros_default.json` | 4 entradas `PROTECAO_CAUDA` |
| 2 | `src/domain/entities/parametro_operacional.py` | 4 entradas em `PARAMETROS_DEFAULT` |
| 3 | `src/ui/desktop/parametros_widget.py` | `_SIDEBAR_ORDER`, `ESTRATEGIA_LABELS`, `ESTRATEGIA_COLORS`, `PARAMETROS_POR_ESTRATEGIA`, `PARAMETROS_INFO`, `_build_param_row` |
| 4 | `src/infrastructure/persistence/database.py` | 14 tuplas em `_migrar_historico_simulacoes` |
| 5 | `src/infrastructure/persistence/repositories/repositories.py` | `salvar_lote()`: 3 listas (colunas, `?`, valores) |
| 6 | `src/ui/desktop/monitor_worker.py` | Import `CalculadoraProtecaoCauda`, método `_resolver_strikes_protecao`, chamada em `_processar_otimizado`, merge `**protecao_campos` |

---

## 6. Ordem de implementação

| Passo | O que | Testável isoladamente? |
|---|---|---|
| 1 | Parâmetros: JSON + entity + widget | Sim — `repo.get_by_chave("limite_protecao_pct")` e conferir sidebar |
| 2 | Colunas no `historico_simulacoes` + `salvar_lote` | Sim — `PRAGMA table_info(historico_simulacoes)` |
| 3 | `_resolver_strikes_protecao()` no worker | Sim — mock do provider de RTD |
| 4 | Chamada `avaliar()` + `protecao_campos` no `_processar_otimizado` | Só com RTD real |
| 5 | Teste ponta-a-ponta | Só com RTD real |

---

## 7. Riscos

- **~240 strikes extras por ciclo** (24 chassis × 10 strikes). Cabe no batch de 500. CAB skip reduz custo.
- **OpenFast sem `BOOK_HEADER`**: fallback para `VOL_ASK` como proxy. `cab_minimo_protecao` controla ambos.
- **Strike inexistente**: calculadora retorna `viavel=False`, sem quebra.
- **Cache de strikes**: limpar em `recarregar_parametros()`. Se um ativo ganha novas séries durante o dia, o cache pode ficar desatualizado — invalidar a cada ~10 ciclos ou quando `flush_buffer()` detectar novos códigos.


---

# Fase 4 — Score de Valor Esperado Ponderado (E[PnL])

**Status:** Planejado — NÃO implementado. Aguardando decisão de execução.

**Objetivo:** Para cada montagem otimizada com proteção, calcular `E[PnL]` integrando sobre as 4 zonas de payoff no vencimento da call, ponderado pela probabilidade log-normal. Permite comparar montagens concorrentes com métrica objetiva de risco/retorno.

## Decisões de design (confirmadas com o usuário em 23/07/2026)

| Decisão | Escolha |
|---|---|
| Ponto de avaliação | Vencimento da CALL (evento crítico, naked expira primeiro) |
| Método de integração | Analítica via `N(d2)` de Black-Scholes (exata, sem erro de grid) |
| Peso no ranking | **Coluna informativa** — NÃO entra no Score automático. O trader decide. |
| Visualização 1 | `ColarCalendarioDialog`: barra sparkline inline com 4 zonas coloridas na grade |
| Visualização 2 | `EstudosCalendarioDialog`: gráfico de payoff existente + barras de probabilidade por zona |
| Visualização 3 | `EngineDashboard`: resumo agregado (quantas montagens com vale < 5%, distribuição de E[PnL]) |

## As 4 zonas de payoff no vencimento da call

```
Zona A: S ≤ K_put          → Put ITM cobre, call OTM, naked sem efeito
Zona B: K_put < S ≤ K_call → Ambas OTM — ganho máximo (prêmio integral)
Zona C: K_call < S < K_prot→ VALE DA MORTE — naked perde, proteção ainda OTM
Zona D: S ≥ K_prot         → Proteção comprada paga, convexidade aparece
```

## Probabilidades (analíticas, via N(d2))

```
P(A) = N(-d2_put)
P(B) = N(d2_put) - N(d2_call)
P(C) = N(d2_call) - N(d2_prot)
P(D) = N(d2_prot)
```

Cada `d2` usa o respectivo strike e a vol implícita da call (`iv_call`).

## PnL esperado em cada zona (aproximação linear no vencimento)

| Zona | PnL Otimizado+Protegido |
|---|---|
| A | base + prêmio_naked_extra |
| B | base + prêmio_naked_extra |
| C | base + prêmio_naked_extra − naked×(S_médio−K_call) − custo_prot |
| D | base + prêmio_naked_extra − naked×(S_médio−K_call) + razão×(S_médio−K_prot) − custo_prot |

Onde `S_médio` é a média truncada da log-normal dentro de cada zona (fórmula fechada via momentos da normal truncada).

## Métrica final

```
E[PnL] = P(A)×PnL_A + P(B)×PnL_B + P(C)×PnL_C + P(D)×PnL_D
E[PnL]/Capital = E[PnL] / capital_empregado   (para comparar entre montagens)
```

## O que o trader vê

**No `ColarCalendarioDialog`** (barra sparkline inline na tabela):
```
PETR4 | Proteção | E[PnL]=R$274 | ██████░░░█░░████
                                     A    B  C    D
                                  (verde)(verde)(verm)(verde)
```

**No `EstudosCalendarioDialog`** (detalhe abaixo do gráfico de payoff):
```
Probabilidades por zona no vencimento da call (24/08/2026, 31 DU):
┌─────────────────────────────────────────────────────┐
│ ████████████████████████████████  Zona A: 72%  +R$200 │
│ ██████                           Zona B: 15%  +R$380 │
│ ██                               Zona C:  3%  -R$150 │  ← vale da morte
│ ████                             Zona D: 10%  +R$120 │
└─────────────────────────────────────────────────────┘
E[PnL] = R$ 274,34  |  E[PnL]/Capital = 0,65%
```

**No `EngineDashboard`:**
```
Proteção de Cauda — Resumo do Ciclo
├─ Montagens com proteção: 12
├─ Viaveis com vale < 5%:  8
├─ E[PnL] médio:           R$ 312
└─ Melhor E[PnL]/Capital:   0,82% (PETR4, Proteção, 1.3×)
```

## Arquivos a tocar

| # | Arquivo | Mudança |
|---|---|---|
| 1 | `calculadora_protecao_cauda.py` | Novo método `_calcular_score_probabilistico()`, campo `score_ev` no `ResultadoProtecaoCauda` |
| 2 | `colar_calendario_dialog.py` | Barra sparkline 4 zonas na coluna da tabela |
| 3 | `estudos_calendario_dialog.py` | Gráfico de barras de probabilidade abaixo do payoff |
| 4 | `engine_dashboard.py` | Resumo agregado de E[PnL] no dashboard |
| 5 | `monitor_worker.py` | Persistir `score_ev` e `score_ev_pct` no `historico_simulacoes` |
| 6 | `database.py` | Migração: colunas `score_ev`, `score_ev_pct` no `historico_simulacoes` |
| 7 | `repositories.py` | Colunas no INSERT de `salvar_lote` |

## Dependências

- **Já implementado (Fases 1-3):** `CalculadoraProtecaoCauda`, `razao_convexidade`, `spread_maximo_pct`, parâmetros por estágio
- **Input necessário:** `ResultadoCaudaAssincrona` (preco_ativo, iv_call, sigma_periodo, dte_call, pnl_com_ratio, pnl_base, breakeven_esquerdo/direito) + `ResultadoProtecaoCauda` (strike_protecao_call/put, custo_protecao, razao_convexidade)
- **já existente:** `pop_upside`/`pop_downside` no `ResultadoColarCalendario` (N(d2) de B&S)

## Ordem de implementação

| Passo | O que | Testável isoladamente? |
|---|---|---|
| 1 | `_calcular_score_probabilistico()` | Sim — teste unitário com chassi sintético |
| 2 | Colunas `score_ev`/`score_ev_pct` no banco | Sim — `PRAGMA table_info` |
| 3 | Persistência no `monitor_worker` | Sim — mock |
| 4 | Sparkline no `ColarCalendarioDialog` | Sim — abrir dialog com resultados mock |
| 5 | Gráfico de barras no `EstudosCalendarioDialog` | Sim — mesmo mock |
| 6 | Resumo no `EngineDashboard` | Sim — mock de resultados |


## Nota operacional: `n_sigma_protecao` × `spread_maximo_pct`

**`n_sigma_protecao` é um piso de corte, não um alvo.** Define "só considere strikes ALÉM deste ponto". Baixar de 2.0 para 1.5 abre mais candidatos (útil quando o book OTM é rarefeito), mas strikes mais próximos do spot tendem a ter spread maior e custo mais alto — viram hedge comum, não seguro de cauda.

**Quem protege isso é o `spread_maximo_pct=0.20`**: se o spread real do book for > 20%, o strike é barrado antes de qualquer conta. Isso permite baixar o `n_sigma` sem medo de comprar caro.

**Recomendação:** comece com 2.0. Se zerar candidatos em muitos ativos, reduza para 1.5. Nunca abaixo de 1.0 — perde-se a assimetria.


---

# Análise de Riscos — Proteção de Cauda Collar Calendário

**Contexto:** Proteção de cauda via compra de opções OTM sobre estrutura de Collar Calendário otimizada por ratio (1.0x a 1.3x na call vendida). 4 variantes por chassi: Base, Rendimento, Platô, Proteção. Sistema de planejamento, não de execução automática.

## 1. Volatilidade estocástica vs σ fixo

**Risco teórico:** Limites baseados em desvio padrão fixo pressupõem estacionaridade — em crises, caudas engordam.

**Realidade Spreadhunter:** O `sigma_periodo` deriva da **volatilidade implícita da call** (IV via B&S reverso do book), não de vol histórica. Mercado em pânico → IV sobe → `s_target = S × (1 + n × σ × √T)` se expande automaticamente. Multiplicador externo (VIX) seria redundante. O sistema também opera por **força bruta** — testa múltiplos ratios e exige PnL > 0 em ±2.2σ. Se o sigma estiver subestimado, a estrutura simplesmente não passa no filtro de ruína.

## 2. Gamma e rolagem da call curta

**Risco teórico:** Em movimentos direcionais fortes, o Gamma da call curta acelera e rolar custa caro.

**Realidade Spreadhunter:** O sistema **não modela rolagem** — assume buy-and-hold até o vencimento. Mas o propósito da proteção não é maximizar PnL: é **trocar perda ilimitada por perda limitada de 2-4%**. Se a estrutura sobrevive a ±2.2σ com PnL > 0, o custo de rolagem é oportunidade perdida, não ruína. A proteção comprada garante o piso.

## 3. Liquidez OTM na B3

**Risco real:** Opções OTM profundas têm spread bid-ask de 30%+ em ativos menores — EV teórico não sobrevive à fricção.

**Cobertura Spreadhunter:** Já implementado (Mudança 3):
- `spread_maximo_pct=0.20`: descarta strikes com spread book real > 20%
- `cab_minimo_protecao`: profundidade mínima de book
- `fator_seguranca_liquidez`: volume diário ≥ múltiplo da ordem
- **Não usa preço teórico** — exige ask/bid reais do Profit RTD ou OpenFast

## 4. Exercício antecipado e dividendos

**Risco real:** Calls americanas podem ser exercidas perto de datas Com.

**Realidade Spreadhunter:** Se exercido na call vendida, o PnL é positivo — a ação já está acima do strike, o exercício **cristaliza um lucro que já existia**. A PUT comprada remanescente é vendida no mercado. O risco é apenas **operacional** (não perceber o exercício a tempo). Cobertura atual:
- Coluna MOD Call (Fase 5): mostra se a call é Americana (A) ou Europeia (E)
- Topbar: exibe datas Com do dia
- A Fase 5 planejada adicionará alerta de cruzamento data-com vs vencimento, mas o risco financeiro é mínimo

| Risco | Cobertura |
|---|---|
| σ não-estacionário | Coberto — IV-based, adaptativo, força bruta |
| Gamma/rolling | Parcial — proteção limita ruína a 2-4%, rolagem não modelada |
| Liquidez OTM | Coberto — filtro de spread real do book |
| Exercício/Dividendos | Parcial — PnL positivo no exercício, MOD visível, falta alerta automático |

**Conclusão:** O sistema é robusto para planejamento. A proteção existe para evitar ruína, não maximizar retorno. Trade-offs conhecidos e documentados.


---

# Fase 5 — Coluna MOD Call (Risco de Exercício Antecipado)

**Status:** Planejado — NÃO implementado.

**Objetivo:** Informar o trader sobre o risco de exercício antecipado da CALL vendida, baseado no MOD (American/European) da call short. PUTs B3 são sempre Europeias — irrelevantes para esta análise.

## As 3 combinações possíveis (só a CALL importa)

| MOD Call Short | MOD Call Proteção | Nome | Ícone | Cor | Significado |
|---|---|---|---|---|---|
| `E` | `E` | **Sem Risco** | 🛡️ `E` | Verde | Ninguém exerce antes do vencimento. Estrutura hermética. |
| `A` | `E` | **Risco Assíncrono** | ⚡ `A` | Âmbar | Pode ser exercido, não pode exercer a proteção. Se exercido, perde a ação e a estrutura quebra. |
| `A` | `A` | **Risco Síncrono** | 🔄 `A` | Azul | Pode ser exercido MAS pode exercer a proteção. Tem ferramenta de manejo, só precisa estar atento. |

Na prática B3, ~99% dos casos caem na linha do meio (`A/E` = âmbar), porque PUTs e a maioria das calls de proteção são Europeias.

## Onde aparece

| Local | Conteúdo |
|---|---|
| **Coluna na grade** (`ColarCalendarioDialog` e `EstudosCalendarioDialog`) | Badge com letra (`A`/`E`) + cor (verde/âmbar/azul) + ícone |
| **Tooltip (hover na coluna)** | Explicação resumida: "Risco MOD — Exercício Antecipado da CALL" |
| **Botão Explicar** | Tabela completa com as 3 combinações, incluindo o alerta sobre vésperas de dividendos |

## Implementação

| Passo | O que |
|---|---|
| 1 | Adicionar coluna `mod_call` na leitura do `importflash.py` (já existe o campo `mod`) |
| 2 | Persistir `mod_call` no `historico_simulacoes` (ou ler do `instrumentos_base` no momento da exibição) |
| 3 | Coluna `MOD Call` nos modelos de tabela (`ColarCalTableModel`, `EstudosCalendarioTableModel`) |
| 4 | Badge delegate para renderizar `A`/`E` com cor |
| 5 | Tooltip e conteúdo do botão Explicar |


---

# Fase 6 — `historico_rejeicoes` (Log de Rejeições Qualificado)

**Status:** Refinado — aguardando implementação após Fase 4.

**Objetivo:** Funil de conversão real para calibrar parâmetros de proteção com dado empírico — não achismo. Saber exatamente em qual estágio cada ativo está travando.

**Design minimalista (5 colunas resolvem 80%):**

| Coluna | Tipo | Descrição |
|---|---|---|
| `ativo` | TEXT | Código B3 |
| `detectado_em` | TIMESTAMP | Data/hora |
| `etapa_rejeicao` | TEXT | Estágio: `liquidez`, `direcao`, `custo`, `cdi`, `spread` |
| `motivo` | TEXT | Frase curta: `custo excede orcamento`, `sem strikes na direcao` |
| `detalhe` | TEXT | Valor quantitativo: `custo=80 orcamento=50`, `spread=35% limite=20%` |
| `sigma_periodo` | REAL | Volatilidade do período (σ√T) no momento da rejeição |
| `iv_call` | REAL | Volatilidade implícita da call (%) |
| `preco_ativo` | REAL | Spot no momento |
| `parametros_snapshot` | JSON | Parâmetros no momento da rejeição |

**Só persiste se:** o chassi não gerou NENHUMA variante viável (nem Base, nem +Tail). Se já tem variante viável, a rejeição de uma específica não agrega informação.

**Snapshot só nos rejeitados.** Nos aprovados, os campos de output do `historico_simulacoes` (`custo_protecao_total`, `score_ev`, `strike_protecao_call`, `viavel`) já bastam para inferir o efeito do parâmetro.

**O que cada estágio de rejeição ensina:**

| Estágio | Aprendizado | Ação |
|---|---|---|
| Liquidez (15) | `fator_seguranca_liquidez` ideal | Calcular percentil 80 do vol real dos rejeitados → definir limiar empírico |
| Direção (16) | `n_sigma_protecao` está longe demais? | Se candidatos líquidos só existem do lado errado, reduzir n_sigma |
| Custo (17) | `limite_protecao_pct` vs preço real de mercado | Se a maioria cai aqui, o orçamento é sistematicamente insuficiente |
| Spread | `spread_maximo_pct` está realista? | Se muitos caem com spread 21-25%, subir de 20% pra 25% resolve |
| CDI (14d) | Grid de ratio está valendo o custo computacional? | Se Rendimento/Proteção/Platô raramente batem a Base, ajustar `otimizado_ratio_max` |

**Consulta agregada típica:**
```sql
SELECT ativo, etapa_rejeicao, COUNT(*) as ocorrencias
FROM historico_rejeicoes
GROUP BY ativo, etapa_rejeicao
ORDER BY ativo, ocorrencias DESC
```
→ Mostra exatamente onde cada ativo está travando. Ajusta UM parâmetro por vez, mede o efeito.

**Isso é estatística descritiva (pandas), não ML.** Entrega calibração de limiar com dado real — não descoberta de padrão oculto, não decisão automática.
