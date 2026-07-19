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
