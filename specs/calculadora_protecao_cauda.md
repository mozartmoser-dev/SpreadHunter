# CalculadoraProtecaoCauda

## Propósito

Camada de proteção de cauda via compra de opções OTM sobre Collar Calendário
otimizado por ratio. Depois que `CalculadoraCaudaAssincrona` encontra o par
(ratio_call, ratio_put) que maximiza %CDI, este módulo avalia se e como proteger
a exposição naked (call ratio > 1.0 ou put ratio < 1.0).

Dois modos:
- **simples:** compra 1 opção OTM por lado, selecionada por eficiência (perda
  evitada / custo). Suporta razão de convexidade no estágio "Proteção".
- **borboleta:** monta Broken Wing Butterfly com 3 strikes reais do book
  (W1 compra + Corpo vende 2× + W2 compra), autofinanciada pelo prêmio do corpo.

Também calcula E[PnL] probabilístico (Fase 4) integrando sobre 4 zonas de payoff
no vencimento da call, ponderado por probabilidade log-normal via N(d2).

## Contrato (Requisitos)

### `avaliar(resultado, strikes_call_candidatos, strikes_put_candidatos, ...)`

**Garante:**
1. Se `naked_call_frac < 2%` E `naked_put_gap < 2%`, retorna `ResultadoProtecaoCauda`
   com `lado_protegido="nenhum"`, `viavel=False`, mas com `score_ev` preenchido
   (E[PnL] da estrutura nua, sem proteção).
2. Caso contrário, avalia cada lado separadamente via `_avaliar_lado` (simples)
   ou `_avaliar_borboleta` (BWB). Retorna `ResultadoProtecaoCauda` com campos
   de custo, quantidade, strike e viabilidade por lado.
3. **Nunca retorna `None`** — mesmo com proteção inviável, retorna struct completa.
4. `pnl_liquido_pos_protecao = pnl_com_ratio - custo_total`.

**Parâmetros de negócio (todos do banco, via `ParametroRepository`):**

| Parâmetro | Default | Unidade | Descrição |
|---|---|---|---|
| `n_sigma_protecao` | 2.0 | σ | Nº de sigmas para s_target |
| `limite_protecao_pct` | 0.35 (35%) | fração | Teto de custo como fração do ganho extra |
| `limite_protecao_pct_rendimento` | 0.20 | fração | **[não implementado]** — ver Decisões |
| `limite_protecao_pct_plato` | 0.45 | fração | **[não implementado]** — ver Decisões |
| `limite_protecao_pct_protecao` | 0.70 | fração | **[não implementado]** — ver Decisões |
| `razao_convexidade_max` | 1.5 | múltiplo | Multiplicador de qtd no estágio "Proteção" |
| `spread_maximo_pct` | 0.20 | fração | Spread bid-ask máximo do book |
| `calda_preco_min_opcao` | 0.01 | R$/ação | Preço mínimo da opção |
| `cab_minimo_protecao` | 1 | contratos | CAB/Volume mínimo |
| `fator_seguranca_liquidez` | 0.2 | múltiplo | Volume diário ≥ qtd_lote × fator |
| `bwb_modo` | "simples" | str | "simples" ou "borboleta" |

**Fórmulas do modo simples (`_avaliar_lado`):**
- `s_target = preco_ativo × (1 ± n_sigma × sigma_periodo)`
- `s_eficiencia = preco_ativo × (1 ± n_sigma × 1.5 × sigma_periodo)`
- `qtd_lote = round(naked_frac × qtd_acao / 100) × 100`  (múltiplo de lote B3)
- `custo = premio_ask × qtd_lote`  (R$)
- `viavel = ganho_extra_ratio > 0 AND custo ≤ ganho_extra_ratio × limite_protecao_pct`

**Fórmulas do modo borboleta (`_avaliar_borboleta`):**
- Alvo = `breakeven_direito` (call) ou `breakeven_esquerdo` (put), fallback para n_sigma
- `custo_por_lote = premio_W1 + premio_W2 − 2 × premio_Corpo`
- `custo_total = custo_por_lote × lotes_bwb × 100`  (R$)
- `viavel = orcamento > 0 AND custo_total ≤ orcamento`

**Fórmulas do E[PnL] (`_calcular_score_probabilistico`):**
- `r_cont = log(1 + taxa_cdi)`, `F = S0 × exp(r_cont × T)`
- Probabilidades por zona via N(d2) mutuamente exclusivas
- Spot esperado condicional via média da log-normal truncada
- PnL linear em cada zona: `credito_total + stock_gain − call_payoff + put_payoff + prot_payoff − custo_prot`

### `_avaliar_lado(lado, naked_frac, strikes_candidatos, ...)`

**Garante:**
1. Filtra strikes por liquidez: `min(vol_ask, vol_bid) ≥ max(cab_minimo, qtd_lote × fator_seguranca_liquidez)`
2. Filtra strikes por spread: `(ask - bid) / ask ≤ spread_maximo_pct` (se bid > 0)
3. Filtra strikes por direção: `strike ≥ s_target` (call) ou `strike ≤ s_target` (put)
4. Seleciona strike por eficiência: `max(perda_evitada / custo)`
5. Se `estagio == "Proteção"`, busca maior `razao_convexidade ≤ razao_convexidade_max`
   que caiba no orçamento (step 0.1, do maior para 1.0).

### `_avaliar_borboleta(lado, naked_frac, strikes_candidatos, ...)`

**Garante:**
1. Requer ≥ 3 strikes na direção para tentar montagem
2. Testa todas as triplas (W1, Corpo, W2) via O(n³) com n ≤ 15 strikes
3. Escolhe a tripla de menor custo total dentro do orçamento
4. **Não filtra por spread** — lacuna conhecida (ver Decisões)

## Decisões Tomadas

### 1. Alvo da borboleta é breakeven, não 2σ
**Porquê:** Diagnóstico em `pendenciascalendario.md` (21/07/2026). Simulação com
PETR4 real mostrou que calls a 2σ têm prêmio elevado demais para o ganho extra
disponível. O alvo correto é o breakeven da estrutura com ratio — onde o prejuízo
começa. Se breakeven não disponível (ex: ratio=1.0), fallback para n_sigma.

### 2. Seleção por eficiência, não proximidade
**Porquê:** Um strike mais distante do target pode ter prêmio muito menor,
resultando em maior perda evitada por real gasto. A métrica
`perda_evitada / custo` captura isso melhor que `min(|strike - target|)`.

### 3. Razão de convexidade só no estágio "Proteção"
**Porquê:** Só o estágio Proteção justifica comprar mais contratos que o mínimo
(razão > 1.0). Nos outros estágios (Base, Rendimento, Platô), a prioridade é
maximizar CDI, não proteção. A razão tenta steps de 0.1 do máximo para 1.0,
parando no primeiro que cabe no orçamento.

### 4. E[PnL] calculado sempre, mesmo sem proteção
**Porquê:** Permite comparar o valor esperado da estrutura nua vs protegida.
Mesmo com `lado_protegido="nenhum"`, o score_ev é preenchido com o E[PnL] da
estrutura sem proteção — útil para ranking entre montagens.

### 5. Custo no modo simples = `premio_ask × qtd_lote` (sem ×100) — consistente com BWB
**Porquê:** Auditado em 05/08/2026, comparando:
- `_avaliar_lado:576` → `custo = premio_ask * qtd_lote`
- `_avaliar_borboleta:694` → `custo_total = custo_por_lote * lotes_bwb * 100`

Com `naked_frac=0.20, qtd_acao=1000`:
- Simples: `qtd_lote=200`, `custo = premio × 200`
- BWB: `qtd_lote=200`, `lotes_bwb = round(200/100) = 2`, `custo_total = custo_por_lote × 2 × 100 = custo_por_lote × 200`

O `×100` na linha 694 compensa a divisão por `_LOTE` na linha 644 (`lotes_bwb = round(qtd_lote / _LOTE)`).
Ambos os modos computam custo como `premio_por_ação × qtd_lote`, mesma unidade.

### 6. Seleção de `limite_efetivo` por `resultado.estagio`
**Porquê:** Implementado em 05/08/2026. Antes, linha 288 usava sempre `limite_protecao_pct`
global, ignorando os 3 parâmetros por variante que o worker já passava. Agora:

```
288:        mapa_limite = {
289:            "Rendimento": limite_protecao_pct_rendimento,
290:            "Platô": limite_protecao_pct_plato,
291:            "Proteção": limite_protecao_pct_protecao,
292:        }
293:        limite_efetivo = mapa_limite.get(resultado.estagio, limite_protecao_pct)
```

Estágios sem entrada no mapa (Base, Otimizado) usam o global como fallback.
4 testes em `TestLimitePorEstagio` confirmam: Rendimento→_rendimento, Platô→_plato,
Proteção→_protecao, Base→global.

### 7. `_avaliar_borboleta` não tem filtro de spread
**Porquê:** [motivo não documentado no código, confirmar com o autor]. O método
não recebe `spread_maximo_pct` na assinatura e não verifica spread bid-ask.
O modo simples (`_avaliar_lado:501-505`) tem o filtro.

**[STATUS: débito conhecido, correção pendente.]**

## Decisões Rejeitadas

### 1. Tratar BWB como compra de proteção pura (débito)
Rejeitado porque a BWB é autofinanciada pelo prêmio das vendas do corpo
(short call do collar). Não faz sentido alocar débito adicional quando o
prêmio do corpo já cobre parcialmente as asas.

### 2. Fallback dentro do próprio módulo para parâmetros
Rejeitado seguindo o padrão do projeto: fallback é responsabilidade do
chamador (`monitor_worker._ler_param_float`). O módulo recebe tudo por
parâmetro explícito.

### 3. Integrar proteção com o Collar Tradicional
Rejeitado porque o Collar Tradicional não tem naked call (ratio fixo = 1.0).
Só Collar Calendário otimizado gera exposição naked relevante.

## Dependências

- `src/domain/services/calculadora_cauda_assincrona.py` → `ResultadoCaudaAssincrona` (input)
- `scipy.stats.norm` → `N(d2)` para probabilidades e E[PnL]
- `math` → `log`, `exp`, `sqrt`
- `json` → serialização de `zonas_ev_json`
- `logging` → diagnóstico de rejeições
- `src/domain/services/pipeline_tracker.py` → `PipelineTracker` (opcional, tracking de estágios)

**Não depende de:**
- Banco de dados (recebe tudo por parâmetro)
- RTD/OpenFAST (os strikes candidatos vêm prontos do worker)
- `calendario_b3` ou `calculadora_custos_b3`

## Cobertura de Teste

**Status: 55 testes em `tests/domain/test_calculadora_protecao_cauda.py`** (10 classes)

| Classe | Testes | Cobre |
|---|---|---|
| `TestExposicaoNula` | 2 | ratio=1.0, naked<2% → "nenhum" |
| `TestApenasCall` | 7 | call-only: strike, qtd, custo, pnl, put zerado |
| `TestApenasPut` | 6 | put-only: strike, qtd, custo, call zerado |
| `TestAmbosLados` | 4 | ambos: custo>0, pnl reduzido, viável |
| `TestSemLiquidez` | 6 | volume insuficiente, unidirecional, zerado |
| `TestLimiteCusto` | 2 | custo excede limite → inviável |
| `TestParametros` | 7 | limite_protecao, cab_minimo, fator_seguranca, qtd_acao |
| `TestChassiReal028ac46c` | 5 | PETR4 real: naked, contratos, custo ask, ganho extra |
| `TestDiagnosticLogs` | 5 | logs de debug em cada ponto de rejeição |
| `TestLimitePorEstagio` | 1 | confirma que usa limite global (não por estágio) |
| `TestRazaoConvexidade` | 5 | só ativa em Proteção, escolhe maior que cabe |
| `TestSelecaoPorEficiencia` | 3 | eficiência vs proximidade |
| `TestFiltroSpread` | 3 | spread largo descarta, aceitável aprova, sem bid ignora |
| `TestScoreEV` | 4 | score_ev viavel vs inviavel, default zero, strikes diferentes |

**Lacunas conhecidas (não cobertas):**
- Modo borboleta (`_avaliar_borboleta`) — 0 testes
- E[PnL] com proteção ativa (só testado com estrutura nua)
- `zonas_ev_json` — serialização não testada
- Pipeline tracker — integração com `_stage` não testada
- `_avaliar_borboleta` com dados OpenFAST reais (vol_ask=0)
- Comportamento com `sigma_periodo ≤ 0` ou `T ≤ 0` no `_calcular_score_probabilistico`
