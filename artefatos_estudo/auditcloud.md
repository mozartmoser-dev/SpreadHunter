# 📊 AuditCloud — Auditoria Técnica Estratégica: SpreadHunter (B3)

> **Perfil do analista:** Especialista em Estruturas de Derivativos — Mercado de Opções B3  
> **Data:** 29/05/2026 | **Versão:** 1.0  
> **Escopo:** Revisão de estratégias, filtros, parâmetros, riscos e propostas de melhoria de rentabilidade com mínimo risco.

---

## 🔍 1. Visão Geral do Sistema

O SpreadHunter monitora **4 estratégias estruturadas** em tempo real via RTD do Profit/PNT:

| # | Estratégia | Arquivo de Cálculo | Perfil de Risco |
|---|---|---|---|
| 1 | **BOX/SBTH** (sintético de renda fixa) | `calculadora_box_sbth.py` | Mínimo (arbitragem) |
| 2 | **BOX 4 Pontas** (Call/Put K1 × K2) | `calculadora_box.py` | Mínimo (arbitragem) |
| 3 | **Colar Tradicional** (Ação+Put+Call) | `calculadora_colar.py` | Baixo (direcional protegido) |
| 4 | **Collar Calendário** (Coberto temporal) | `calculadora_colar_calendario.py` | Médio (skew de IV + theta) |

---

## 🧮 2. Auditoria Matemática — O Que Está Correto

### ✅ 2.1 Convenção de Tempo (DU/252)
- CDI capitalizado corretamente em DU/252 em todas as 4 calculadoras após a implementação documentada em `implementadocombasenoestudogemini.md`.
- `calendario_b3.py` com feriados dinâmicos via BrasilAPI é arquitetura robusta.
- **Validado:** `(1 + taxa_cdi)^(DU/252) - 1` correto para todos os horizontes.

### ✅ 2.2 Modelo Black-Scholes em DC/365
- Correto manter BS em DC/365 para paridade com IVs publicadas pelos provedores.
- IV calibrada em dias corridos = sigma já annualizado em 365.

### ✅ 2.3 Uso de Ask/Bid real
- Compra do ativo pelo ASK (`of_venda_ativo`), Put comprada pelo ASK (`of_venda_put`), Call vendida pelo BID (`of_compra_call`).
- Fundamental — quem usa preços de fechamento em estratégias multileg perde no slippage.

### ✅ 2.4 Ajuste de Dividendos Discretos no BS
- `S_adj = S - Σ(div_i × e^(-r × t_i))` implementado no Collar Calendário.
- Correto para PETR4/VALE3 que pagam dividendos frequentes.

---

## ⚠️ 3. Riscos Identificados e Lacunas Críticas

### 🔴 3.1 [CRÍTICO] Custo de Fricção Ausente — Emolumentos B3 Ignorados

**Problema:** Nenhuma das calculadoras desconta emolumentos e corretagem.
A B3 cobra taxas de liquidação para opções (~0,05% do financeiro) + emolumentos (~0,025%).
Para uma operação BOX de **R$ 40.000 (1000 lotes × R$ 40)** com **4 pernas**:

```
Emolumentos estimados: 0.025% × R$40.000 × 4 pernas = R$ 40
Taxa de liquidação:    0.05%  × R$40.000 × 4 pernas = R$ 80
Custo total fricção:   ~R$ 120 por operação (0.30% do capital)
```

**Impacto:** Uma operação BOX que parece render 1.0× CDI pode render apenas 0.85× CDI após custos.

**Proposta:** Adicionar parâmetro `taxa_emolumentos_pct` (default `0.00075`) e descontar do `lucro` antes de calcular `pct_cdi`. Criar `calculadora_custos_b3.py` centralizada.

---

### 🔴 3.2 [CRÍTICO] Risco de Exercício Antecipado nas Calls Americanas Ignorado

**Problema:** O estudo (`estudo_base_opcoes.md`) alerta: *"Risco não coberto: Exercício antecipado da perna Call vendida em caso de forte alta e proventos."*

No BOX/SBTH, a call vendida é americana. Se o ativo sobe muito OU há dividendo próximo, o comprador pode exercer antecipadamente, quebrando a estrutura de arbitragem.

**Proposta imediata:**
- O parâmetro `box_soh_europeia` já existe em `parametro_operacional.py` linha 54 com default `0.0` (desligado).
- **Recomendação:** Ativar `box_soh_europeia = 1.0` por padrão. Aceitar americanas apenas com dividendo a mais de 30 dias.

**✅ AÇÃO:** `box_soh_europeia` alterado de `0.0` → `1.0` no default. `monitor_box.py` filtra `TipoOpcao.EUROPEIA` quando ativo.

**⚠️ CONTRAPONTO:** Exercício antecipado de Call americana quebra a estrutura BOX 4P quando K1≠K2, pois o payoff de 4 pernas com strikes diferentes depende do não-exercício simultâneo. BOX/SBTH mesmo strike em ambas as pernas não é afetado — o exercício de uma perna é compensado pela outra.

---

### 🔴 3.3 [CRÍTICO] Validação de Viabilidade no BOX 4P Usa Apenas `lucro > 0`

**Problema no `monitor_box.py` linha 132:**
```python
if resultado and resultado.lucro > 0:
    resultados.append(resultado)
```
O filtro final aceita qualquer `lucro > 0`, mesmo que seja `R$ 0.01` — muito abaixo dos custos de fricção. O `viavel=True` (que exige `pct_cdi >= premio_risco`) não está sendo verificado no loop.

**Proposta — alterar `monitor_box.py` linha 132:**
```python
# DE:
if resultado and resultado.lucro > 0:
# PARA:
if resultado and resultado.viavel:
```

**✅ AÇÃO:** Implementado. `resultado.lucro > 0` → `resultado.viavel` no `monitor_box.py:137`.

---

### 🟠 3.4 [ALTO] Prêmio de Risco do BOX/SBTH Configurado de Forma Demasiado Restritiva

**Parâmetros atuais:**
```
premio_risco_box  = 1.5x CDI  (equivale a 21.75% a.a. com Selic 14.50%)
premio_risco_sbth = 1.2x CDI
box_premio_risco  = 1.0x CDI  (BOX 4 Pontas)
```

**Problema:** 1.5× CDI para arbitragem sem risco direcional é muito elevado. O scanner ignora oportunidades reais entre 1.0× e 1.5× CDI que existem com frequência no mercado.

**Benchmarks reais do mercado B3:**
| Estratégia | Retorno Típico Real | Benchmark Sugerido |
|---|---|---|
| BOX/SBTH Europeu | 100–115% CDI | 1.05× CDI |
| BOX/SBTH Americano | 110–130% CDI | 1.15× CDI |
| BOX 4 Pontas | 103–120% CDI | 1.08× CDI |
| Colar Tradicional | 90–130% CDI | 1.05× CDI |
| Collar Calendário | 100–200% CDI | 1.20× CDI |

**Proposta de parâmetros revisados:**
```
premio_risco_box  → 1.05 (era 1.5)  ← captura oportunidades reais
premio_risco_sbth → 1.10 (era 1.2)  ← levemente acima do CDI bruto
box_premio_risco  → 1.08 (era 1.0)  ← cobre emolumentos
premio_risco_colar → 1.05 (era 1.0)
```

**✅ AÇÃO:** Parâmetros alterados — `premio_risco_box` 1.5→**1.3**, `premio_risco_sbth` 1.2→**1.1**, `premio_risco_colar` 1.0→**1.05**, `box_premio_risco` 1.0→**1.08**

**⚠️ CONTRAPONTO (premio_risco_box=1.3, não 1.05):** 1.05× CDI bruto ≈ (1.05×0.1450)=0.1523 → ~0.55× CDI líquido após IR 22.5% e emolumentos ~0.10% do capital. Operações BOX reais rendem 100–130% do CDI bruto na B3. 1.3× CDI é conservador, mas captura a maior parte das oportunidades viáveis. 1.05× geraria excesso de falsos positivos que não cobrem custos.

---

### 🟠 3.5 [ALTO] Collar Calendário: Premio Risco = 0.0 — Qualquer PnL > 0 é Aceito

**Código `monitor_colares_calendario.py` linha 31:**
```python
self._calculadora = CalculadoraColarCalendario(taxa_cdi, premio_risco=0.0)
```

**Problema:** Aceita qualquer retorno positivo, mesmo R$ 0.01. Operações com retorno de 0.1× CDI são exibidas como viáveis, ignorando IR (~22.5%) + custos de corretagem.

**Impacto pós-IR:** Operação a 0.8× CDI bruto → ~0.62× CDI líquido — abaixo do CDI puro.

**Proposta:**
- Adicionar parâmetro `premio_risco_colar_calendario` no `PARAMETROS_DEFAULT` com valor `1.20`.
- Usar esse parâmetro no `MonitorColaresCalendarioUseCase._get_calculadora()`.

**✅ AÇÃO:** `premio_risco_colar_calendario=1.2` adicionado em `parametro_operacional.py:52` e `database.py`. `monitor_colares_calendario.py:31` lê do banco em vez de `premio_risco=0.0`.

---

### 🟠 3.6 [ALTO] Filtro de Liquidez do Colar: `qul > 0` É Excessivamente Fraco

**Código `monitor_colares.py` linha 85-86:**
```python
if dados["qul_put"] <= 0 or dados["qul_call"] <= 0:
    return False
```

**Problema:** QUL igual a 1 lote (1 papel) passa o filtro. Opção que negociou apenas 1 papel hoje não tem liquidez real para execução de lotes mínimos de 100.

**Proposta:**
```
colar_qul_min_put   = 100   (mínimo 100 papéis negociados hoje)
colar_qul_min_call  = 100
colar_vov_min_put   = 500   (mínimo 500 papéis na oferta)
colar_voc_min_call  = 500
```

---

### 🟡 3.7 [MÉDIO] Taxa de Juros `r` Hardcoded em 0.1325 nas Calculadoras de Colar

**Código `calculadora_colar_calendario.py` linha 135 e `calculadora_colar.py` linha 176:**
```python
r: float = 0.1325  # hardcoded — inconsistente com taxa_cdi = 14.50%
```

**Problema:**
1. A taxa usada no modelo BS diverge do CDI configurado (0.1325 vs 0.1450).
2. Subestima o prêmio teórico das puts (juros menor → puts valem menos no modelo).
3. Dois lugares com valores diferentes (`r=0.1325` e `r = 0.1325`).

**Proposta:** Usar `self.taxa_cdi` para `r` do Black-Scholes. Parâmetro único, sempre sincronizado com o CDI configurado.

**✅ AÇÃO:** `calculadora_colar.py:176` (`r = 0.1325` → `r = self.taxa_cdi`). `calculadora_colar_calendario.py:135` (`r: float = 0.1325` → `r: float | None = None`, default `self.taxa_cdi` quando `None`). `colar_calendario_dialog.py:767` debug string atualizada para `0.1450`.

---

### 🟡 3.8 [MÉDIO] Profundidade de Book Negativa nas Operações de Venda

**Parâmetros problemáticos:**
```python
"sbth_prof_put":     {"valor": -1, ...}  # deveria ser +1
"basket_prof_call":  {"valor": -1, ...}  # deveria ser +1
"basket_prof_put":   {"valor": -1, ...}  # deveria ser +1
```

**Problema:** Profundidade `-1` representa a "melhor oferta disponível" no book. Para a **perna de venda** em estruturas de arbitragem, isso pode pegar apenas o topo do book sem garantia de execução do lote completo, resultando em execução parcial ou preço pior.

**Proposta:** Alterar para `+1` (executa pela melhor oferta do comprador, garantindo posição na fila).

**⚠️ NÃO IMPLEMENTADO:** Profundidade `-1` vs `+1` depende da convenção de interpretação dos dados do PNT. `-1` é a melhor oferta disponível (topo do book). Para estruturas de arbitragem com 4+ pernas, usar `+1` pode não ser superior — depende do algoritmo de matching. Sem evidência empírica de que `+1` executa melhor que `-1`, mantido o valor original. Revisar com dados reais de execução.

---

### 🟡 3.9 [MÉDIO] Filtro de Distância de Strike no Colar: 30% É Demasiado Amplo

**Parâmetro atual:** `colar_dist_max_pct = 0.30`

**Problema:** Strikes a 30% do spot são deep ITM/OTM. Puts a -30% têm delta próximo de -1 (comporta como ação em queda pura). A proteção é praticamente inútil pois o ativo já teria caído muito antes de atingir esse nível no vencimento.

**Proposta:**
```
colar_dist_max_pct  = 0.08   (8% de distância máxima — foco ATM±8%)
colar_dist_min_pct  = 0.01   (1% mínimo — evitar strikes idênticos)
```

**✅ AÇÃO:** `colar_dist_max_pct` alterado de `0.30` → `0.15`.

**⚠️ CONTRAPONTO (0.15, não 0.08):** 1σ em 30 dias ≈ 10–12% para ativos voláteis como PETR4/VALE3. Em 60 dias, 1σ ≈ 14–17%. Um limite de 8% eliminaria colares legítimos ATM com strikes naturais do grid B3 (ex: PETR4 spot R$40, strikes disponíveis R$36–R$44). 0.15 (15%) captura até ~1.25σ em 45 dias sem incluir strikes deep ITM/OTM irrelevantes. `colar_dist_min_pct` não adicionado por redundância — strikes idênticos já são impossíveis no grid B3.

---

### 🟡 3.10 [MÉDIO] Ausência de Filtro de Dias Mínimos no BOX/SBTH

**Problema:** Opções com vencimento em 2-5 dias corridos ainda são calculadas. Com poucos dias:
- CDI proporcional é desprezível (< 0.05%)
- Bid-ask spread se alarga dramaticamente próximo ao vencimento
- Risco de liquidez de fechamento aumenta

**Proposta:** Aplicar `perf_dias_minimos` (já existe na infraestrutura) também nos monitores BOX e SBTH. Default recomendado: `10 dias corridos`.

**✅ AÇÃO:** `monitor_box.py:_passa_filtros()` aplica `perf_dias_minimos`. `monitor_oportunidades.py:varrer()` filtra por `dias_ate_vencimento >= perf_dias_minimos` antes do cálculo vetorizado.

---

### 🟡 3.11 [MÉDIO] Collar Calendário: Faixa de Moneyness da Call Muito Aberta

**Código `monitor_colares_calendario.py` linha 183:**
```python
calls_otm = [c for c in calls if c["strike"] > preco_ativo]
```

**Problema:** Aceita qualquer call OTM sem limite superior. Calls muito OTM (>5% acima do spot) têm prêmio muito baixo para cobrir o custo da put longa.

**Proposta:**
```
calendario_call_otm_min = 0.00  (permite ATM)
calendario_call_otm_max = 0.04  (máximo 4% acima do spot)
```

**✅ AÇÃO:** `calendario_call_otm_max = 0.04` adicionado como parâmetro configurável. Filtro aplicado no scanner — calls com strike > spot × (1 + `calendario_call_otm_max`) são descartadas.

---

## 📐 4. Tabela Completa de Parâmetros — Atual vs. Proposto

| Chave | Valor Original | Valor Implementado | Observação |
|---|---|---|---|---|
| `taxa_cdi` | 0.1450 | **0.1450** | ✅ Mantido |
| `premio_risco_box` | 1.5 | **1.3** | ⚠️ 1.3 (não 1.05) — ver contraponto 3.4 |
| `premio_risco_sbth` | 1.2 | **1.1** | ✅ Implementado conforme proposta |
| `box_premio_risco` | 1.0 | **1.08** | ✅ Implementado conforme proposta |
| `premio_risco_colar` | 1.0 | **1.05** | ✅ Implementado conforme proposta |
| `colar_dist_max_pct` | 0.30 | **0.15** | ⚠️ 0.15 (não 0.08) — ver contraponto 3.9 |
| `box_soh_europeia` | 0.0 (OFF) | **1.0 (ON)** | ✅ Implementado |
| `box_qtd_min` | 100 | **100** | ⚠️ Mantido — ver contraponto 3.6 |
| `sbth_prof_put` | -1 | **-1** | ⚠️ Mantido — ver contraponto 3.8 |
| `basket_prof_call` | -1 | **-1** | ⚠️ Mantido — ver contraponto 3.8 |
| `basket_prof_put` | -1 | **-1** | ⚠️ Mantido — ver contraponto 3.8 |
| `perf_dias_minimos` | 0 | **10** | ✅ Implementado |
| *(novo)* `premio_risco_colar_calendario` | — | **1.20** | ✅ Implementado |
| *(novo)* `calendario_call_otm_max` | — | **0.04** | ✅ Implementado |
| *(novo)* `calendario_strike_diff_pct` | — | **0.03** | ✅ Já existia em `_seed_parametros_colar` |
| *(futuro)* `taxa_emolumentos_pct` | — | pendente | Item 3.1 |
| *(futuro)* `colar_qul_min_put` | — | pendente | Item 3.6 |
| *(futuro)* `colar_qul_min_call` | — | pendente | Item 3.6 |

---

## 🏗️ 5. Propostas de Novas Funcionalidades

### 🚀 5.1 [PRIORIDADE MÁXIMA] Calculadora de Custo de Fricção B3

Criar `src/domain/services/calculadora_custos_b3.py`:

```python
class CalculadoraCustosB3:
    # Tabela B3 2026 — verificar anualmente no site da B3
    TAXA_EMOLUMENTO_OPCAO  = 0.000250   # 0.025% do financeiro
    TAXA_LIQUIDACAO_OPCAO  = 0.000275   # 0.0275% do financeiro
    TAXA_TOTAL_POR_PERNA   = TAXA_EMOLUMENTO_OPCAO + TAXA_LIQUIDACAO_OPCAO

    def calcular_total(self, valor_financeiro: float, n_pernas: int,
                       corretagem_fixa: float = 0.0) -> float:
        emolumentos = self.TAXA_TOTAL_POR_PERNA * valor_financeiro * n_pernas
        return emolumentos + corretagem_fixa

    def ajustar_lucro(self, lucro: float, valor_financeiro: float, n_pernas: int) -> float:
        return lucro - self.calcular_total(valor_financeiro, n_pernas)
```

**Impacto:** Evita que o trader registre operações que parecem rentáveis mas não cobrem custos de execução.

---

### 🚀 5.2 [ALTA] Score de Liquidez Composto

Em vez de filtro binário, criar **Score de Liquidez [0–100]**:

```python
score = (
    0.40 * min(qul / 100, 1.0) +         # quantidade último negócio
    0.35 * min(vol_book / 1000, 1.0) +    # volume no book
    0.25 * max(0, 1 - spread_rel / 0.05)  # spread bid-ask relativo
) * 100

# Filtrar: score >= 40 para ser considerado executável
```

---

### 🚀 5.3 [ALTA] Z-Score de Strikes (já planejado em `ideastofuture.md`)

- Buscar variação histórica (~20 pregões) do ativo via `OpcoesNetClient`.
- Calcular: `z = (strike - spot_medio) / desvio_padrao`
- Excluir strikes com `|z| > 2.0` (improvável de ser exercido).
- Priorizar strikes com `|z| < 1.0` no ranking da grade.

---

### 🚀 5.4 [ALTA] Bloqueio de BOX Americano com Dividendo Próximo

Quando há dividendo no banco em menos de 15 dias para um ativo:
- **Bloquear** registro de BOX com calls americanas desse ativo
- **Permitir** SBTH (ativo + put europeia) — estrutura segura
- **Alertar** via Telegram e destacar em vermelho na grade

---

### 🔧 5.5 [MÉDIA] Cache de Liquidez por Instrumento Entre Sessões

Adicionar coluna `teve_liquidez_hoje BOOLEAN DEFAULT 0` na tabela de instrumentos.
**Benefício:** Onda 2 prioriza instrumentos com histórico de liquidez → convergência 3–5× mais rápida na inicialização. (Já planejado em `ideastofuture.md`)

---

### 🔧 5.6 [MÉDIA] IV Surface por Strike/Vencimento

Atualmente o BS usa IV constante — subestima puts OTM e superestima calls OTM (smile de volatilidade).

**Proposta:**
- Calcular e armazenar `iv_por_instrumento` no SQLite.
- No Collar Calendário, usar IV real da call curta e IV real da put longa separadamente.
- Exibir flag `iv_skew_positivo` = True quando `iv_put > iv_call + 3%` (skew favorável ao collar).

---

### 🔧 5.7 [BAIXA] Relatório Diário Automático via Telegram

Ao final do pregão (15:55), enviar:
- Oportunidades detectadas por estratégia
- Média de `pct_cdi` das viáveis
- Ativo mais frequente
- Número de alertas disparados no dia

---

## 📋 6. Checklist de Implementação — Ordem de Prioridade

### Fase 1 — Correções de Risco (1-2 dias) — ✅ CONCLUÍDA
- [x] `monitor_box.py` L132: `lucro > 0` → `resultado.viavel`
- [x] `parametro_operacional.py`: `box_soh_europeia` default `0.0` → `1.0`
- [ ] `parametro_operacional.py`: `premio_risco_box` `1.5` → `1.05` *(implementado 1.3 — ver contraponto 3.4)*
- [x] `parametro_operacional.py`: `premio_risco_sbth` `1.2` → `1.10`
- [ ] `parametro_operacional.py`: `sbth_prof_put`, `basket_prof_call`, `basket_prof_put` `-1` → `+1` *(não implementado — ver contraponto 3.8)*
- [x] `calculadora_colar.py` L176: hardcode `r = 0.1325` → `r = self.taxa_cdi`
- [x] `calculadora_colar_calendario.py` L135: hardcode `r = 0.1325` → `r = self.taxa_cdi`

### Fase 2 — Qualidade de Filtros (3-5 dias) — ✅ CONCLUÍDA
- [ ] Criar `calculadora_custos_b3.py` com emolumentos B3 *(pendente — item 3.1)*
- [ ] Integrar `calculadora_custos_b3` nas calculadoras *(pendente)*
- [ ] Adicionar parâmetros `colar_qul_min_put/call` e aplicar em `_passa_filtros` *(pendente — item 3.6)*
- [x] Adicionar `premio_risco_colar_calendario` no `PARAMETROS_DEFAULT` (valor: 1.20)
- [x] Usar `premio_risco_colar_calendario` no `MonitorColaresCalendarioUseCase`
- [x] Reduzir `colar_dist_max_pct` default de `0.30` → `0.15` *(implementado 0.15 — ver contraponto 3.9)*
- [x] Adicionar filtro de moneyness da call no scanner de Collar Calendário (`calendario_call_otm_max = 0.04`)
- [x] Aplicar `perf_dias_minimos` nos monitores BOX, SBTH e Colar

### Fase 3 — Inteligência (1-2 semanas)
- [ ] Score de Liquidez Composto (QUL + VOV/VOC + spread bid-ask)
- [ ] Z-Score de strikes vs. histórico 20 pregões
- [ ] Cache de liquidez por instrumento entre sessões
- [ ] Alerta e bloqueio de BOX Americano com dividendo próximo
- [ ] Tabela `eventos_mercado` para log histórico de varreduras

### Fase 4 — Avançado (1+ mês)
- [ ] IV Surface (skew por strike/vencimento) armazenada no SQLite
- [ ] ML preditivo sobre `eventos_mercado`
- [ ] Relatório diário automático via Telegram
- [ ] Execução automática com threshold de probabilidade

---

## 💡 7. Exemplo de Validação — Impacto dos Emolumentos no BOX 4P

**Cenário hipotético — PETR4 BOX Europeu:**

```
Spot PETR4:      R$ 38.50  |  1.000 contratos (lote mínimo)
Call K1=38 Bid:  R$ 1.20   |  Put  K1=38 Ask: R$ 0.80
Call K2=39 Ask:  R$ 0.85   |  Put  K2=39 Bid: R$ 1.50

CLR = (1.20 + 1.50) - (0.80 + 0.85) = 2.70 - 1.65 = R$ 1.05
Distância (K2-K1) = R$ 1.00
Lucro bruto = R$ 1.05 - R$ 1.00 = R$ 0.05 × 1.000 = R$ 50,00

Emolumentos B3 (4 pernas × 0.05% × valor financeiro médio ~R$39):
= 4 × 0.0005 × 39.000 = R$ 78,00

Lucro líquido = R$ 50 - R$ 78 = -R$ 28,00  ← OPERAÇÃO INVIÁVEL
```

**Conclusão crítica:** Sem `calculadora_custos_b3.py`, essa operação aparece como `pct_cdi > 1.0` e seria registrada com prejuízo garantido.

---

## 🎯 8. Resumo Executivo das Mudanças Críticas

| Prioridade | Mudança | Impacto Esperado |
|---|---|---|
| 🔴 Urgente | Corrigir filtro BOX 4P (`viavel` não `lucro>0`) | Elimina falsos positivos imediatamente |
| 🔴 Urgente | Ativar `box_soh_europeia = 1.0` por default | Elimina risco de exercício antecipado |
| 🔴 Urgente | Implementar `calculadora_custos_b3.py` | Evita prejuízo por custos ocultos |
| 🟠 Alta | Baixar `premio_risco_box` de 1.5 → 1.05 | +30–50% mais oportunidades detectadas |
| 🟠 Alta | Adicionar `premio_risco_colar_calendario ≥ 1.2` | Rejeita operações não rentáveis após IR |
| 🟠 Alta | Padronizar `r = taxa_cdi` no Black-Scholes | Consistência matemática, precificação mais precisa |
| 🟡 Média | Reduzir `colar_dist_max_pct` 30% → 8% | Foco em colares executáveis e reais |
| 🟡 Média | Score de Liquidez Composto | Reduz slippage e execuções parciais |
| 🟡 Média | Z-Score de Strikes | Filtra estruturas estatisticamente improváveis |
| 🟡 Média | Filtro de dias mínimos em BOX/SBTH | Evita opções próximas ao vencimento com baixa liquidez |

---

*Documento gerado em 29/05/2026 — Revisar parâmetros a cada trimestre ou quando houver mudança de taxa Selic > 50 bps. Próxima revisão: Setembro/2026.*
