# Collar Calendário Estrutural Calda Assíncrona
## Protocolo Delta Estrutural Híbrido (Terceira Visão)

### Status: Estudo — Nenhuma alteração de código

---

## Arquitetura Atual (Colar Calendário Coberto — Existente)

**3 pernas**: Comprar Ação + Vender CALL curta + Comprar PUT longa

**Objetivo**: Lucrar da diferença de decay temporal (theta) entre a CALL curta e a PUT longa.

**Fluxo existente** (`monitor_colares_calendario.py`):
1. Filtrar instrumentos por DTE, strike RTD, liquidez QUL
2. Classificar: DTE ≤ dte_call_max → candidato a CALL; DTE > dte_call_max → candidato a PUT
3. Parear por distância de strike (`calendario_strike_diff_max`) + spread DTE (`dte_extra_min`/`max`)
4. Calcular viabilidade via `CalculadoraColarCalendario.calcular()`:
   - IVs via Black-Scholes (Brent)
   - Gregas (delta, theta, vega, gamma)
   - PnL projetado no vencimento da CALL
   - Custos B3 + IR (15%)
   - % CDI = PnL bruto / capital / CDI_periodo
   - Viável se % CDI >= premio_risco_colar_calendario
5. Scoring (theta, CDI, sigma, crédito, liquidez)

---

## Nova Especificação — Correção de Leitura

**O documento não é sobre filtro — é sobre otimização de ratio para bater uma meta de CDI.**

### Algoritmo Central (determinístico, sem loop)

```
Para cada par viável (call, put, ativo) vindo da calculadora existente:
  1. PnL_base = ResultadoColarCalendario.pnl_projetado (ratio 1:1:1)
  2. Selic_periodo = (1 + taxa_cdi)^(dte_call/252) - 1
  3. Target_ROI = Selic_periodo × calda_premio_risco
  4. Capital_base = ResultadoColarCalendario.capital_empregado
  5. PnL_alvo = Capital_base × Target_ROI
  6. Gap = PnL_alvo - PnL_base
  
  Se Gap <= 0 → estrutura já bate o alvo, mostra como está.
  Se Gap > 0:
    7. K_3σ = S₀ + 3 × S₀ × σ_IV × √(dte_call/252)
    8. Preço_CALL_3σ = BS(S₀, K_3σ, dte_call, r, σ_IV, 'call')
    9. Ratio_extra = ceil(Gap / Preço_CALL_3σ)
    10. Ratio_total = 1 + Ratio_extra  (ex: 1 + 30,5 = 31,5)
    11. Recalcular PnL com Ratio_total
    12. Validar cenário de estresse com Ratio_total:
        PnL_stress = (S₀×0.70 - Net₀×ratio) + max(0, K_P - S₀×0.70)
        assert PnL_stress > 0
```

### Chassis Yang Xu (Seção 2 do documento) → Define σ para o cálculo de K_3σ

O chassis Média-Variância não define alavancagem — define a **volatilidade referência**:
- σ = 0.0635 (6.35% anualizado)
- Usado para calcular o desvio padrão no período: `σ_p = σ × √(dte_call/252)`
- K_3σ = S₀ × (1 + 3 × σ_p)
- Se σ_IV da opção for maior que σ do chassis, usar σ_IV (conservador)

---

## Parâmetros Novos

| Chave | Default | Grupo | Descrição |
|-------|---------|-------|-----------|
| `calda_habilitado` | 0 | COLLAR_CALENDARIO_CAUDA | Habilitar variante Cauda Assíncrona |
| `calda_premio_risco` | 2.5 | COLLAR_CALENDARIO_CAUDA | Múltiplo do CDI para target de retorno |
| `calda_sigma_chassis` | 0.0635 | COLLAR_CALENDARIO_CAUDA | Volatilidade anualizada do chassis Yang Xu |
| `calda_desvios_cauda` | 3.0 | COLLAR_CALENDARIO_CAUDA | Nº de desvios para o strike de cauda |
| `calda_ratio_max` | 50.0 | COLLAR_CALENDARIO_CAUDA | Ratio máximo permitido (proteção contra ratios absurdos) |
| `calda_preco_min_call_cauda` | 0.01 | COLLAR_CALENDARIO_CAUDA | Preço mínimo da CALL de cauda (R$, abaixo disso considerar ilíquida) |

---

## Modelo de Dados — ResultadoCaudaAssincrona (Novo DTO)

```
ResultadoCaudaAssincrona:
  # Herda campos base do par (ativo, strikes, DTEs, IVs, etc.)
  ativo: str
  strike_call: float
  strike_put: float
  dte_call: int
  dte_put: int
  preco_ativo: float
  iv_call: float
  iv_put: float
  
  # Campos específicos da Cauda
  pnl_base: float          # PnL 1:1:1 da calculadora existente
  pnl_alvo: float          # Target ROI × capital
  gap: float               # PnL_alvo - PnL_base
  strike_cauda: float      # K_3σ = S₀ + 3 × σ × √(t)
  preco_call_cauda: float  # BS price no strike K_3σ
  ratio_extra: int         # ceil(gap / preco_call_cauda)
  ratio_total: float       # 1 + ratio_extra
  pnl_com_ratio: float     # PnL recalculado com ratio_total
  pnl_stress: float        # PnL no cenário -30% com ratio_total
  stress_ok: bool          # pnl_stress > 0
  viavel: bool             # stress_ok AND ratio_total <= calda_ratio_max
  score_cauda: float       # ponderado por pnl_com_ratio / gap
```

---

## Integração sem Tocar no Fluxo Existente

```
Worker (a cada ~9s):
  1. monitor_colares_calendario.varrer()  →  lista ResultadoColarCalendario (intocado)
  2. Se calda_habilitado:
       para cada resultado viável:
         cauda = CalculadoraCauda.calcular(resultado)
         se cauda.viavel: adiciona à lista_cauda
  3. Emite colares_calendario_atualizados (intocado)
  4. Emite cauda_atualizados (novo signal)
```

**Zero BS extra, zero IV duplicado.** A `CalculadoraCauda` só faz álgebra linear em cima dos campos do `ResultadoColarCalendario` + uma chamada `black_scholes(S₀, K_3σ, ..., 'call')` — que é a mesma fórmula já usada na calculadora principal (pode reusar a função).

---

## Observações

- **Option A vs Option B do estudo**: Option B (cauda a 3σ) é a implementada pelo algoritmo acima. Option A (ratio 1,1 no strike ATM) seria útil como fallback se o preço da CALL a 3σ for zero ou o ratio estourar o limite.
- O preço da CALL a 3σ é tipicamente muito baixo (centavos), então ratios altos são esperados (30:1, 40:1). O parâmetro `calda_ratio_max` evita loucuras.
- A liquidez da CALL a 3σ é questionável — o parâmetro `calda_preco_min_call_cauda` filtra strikes sem depth.
