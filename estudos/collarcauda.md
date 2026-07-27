# Estratégia Collar Calendário + Cauda Assíncrona (Híbrido Estrutural)

## Data: 09/07/2026

## Contexto e Objetivo
O Collar Calendário Neutro (1:1:1) entrega `pct_cdi_base` entre 2.0x e 2.5x CDI nos pares de VALE3 e PETR4 atualmente. O usuário deseja **esticar o prêmio** vendendo **CALLs extras no mesmo strike** para atingir um alvo maior (≥3x CDI), mantendo manobralidade (breakeven em ≈3σ, ou melhor, PnL positivo em **toda cauda de ±3σ**).

A rotina de Cauda Assíncrona (`CalculadoraCaudaAssincrona` em `src/domain/services/calculadora_cauda_assincrona.py`) deveria, a partir de cada par viável do Collar Calendário (`monitor_colares_calendario.py` → `MonitorWorker._processar_cauda()`), encontrar a **menor razão** de CALLs extras (`n ∈ ℕ, n ≥ 1`) que atinja `pct_cdi_ratio ≥ calda_premio_risco` com **validação de stress** (PnL > 0 em ±3σ).

## Problema Identificado
Hoje a rotina **não dispara nenhuma variante** para pares com `pct_cdi_base` entre 2.0x e 2.5x (viáveis no monitor). Causas:

1. **Trava `be >= k_3sigma` (linha 99)**: O breakeven superior com ratio > 1 é calculado como `be = (n×(Kc+Pc) - S₀ - Pp) / (n-1)`. Para `n` alto e `k_3sigma` dependente de IV, é comum `be < k_3sigma` → `return None` silencioso.
2. **Loop em `range(1, calda_ratio_max + 1)` (linha 85)**: `calda_ratio_max` era 70 (agora 40 no banco). O usuário quer que `40` represente **+40% de escala** (ratio max = 1.4x), não 40x.
3. **`gap ≤ 0` (linha 73–74)**: `target_pnl = capital_base × cdi_periodo × calda_premio_risco`. Para `pct_cdi_base = 2.3x` e `calda_premio_risco = 3.0`, `gap` é negativo pois o par já entrega mais que o alvo, mas a rotina retorna `None` sem considerar que talvez o usuário **queira mais prêmio mesmo acima do alvo**.
4. **Sem validação por range**: o usuário quer PnL > 0 em **todo o intervalo de ±3σ** (não apenas `be >= k_3sigma`).

## Parâmetros (definidos pelo usuário para operar)

| Parâmetro | Valor | Descrição |
|---|---|---|
| `calda_habilitado` | 1.0 | Habilitar cauda |
| `calda_premio_risco` | 3.0 | Alvo mínimo de CDI para a variante com cauda (≥3.0x) |
| `calda_desvios_cauda` | 3.0 | Nº de desvios para o strike de cauda (critério de manobralidade) |
| `calda_ratio_max` | 40% (1.4x) | Escala máxima = +40% de CALLs vendidas sobre o base 1:1:1 |
| `premio_risco_colar_calendario` | 2.0 | Filtro do monitor (viabilidade base) |
| `taxa_cdi` | 14.25% | Taxa CDI |
| Lote de CALLs | **1 CALL avulsa** (não múltiplo de 100) | A cauda vende CALLs individuais, sem restrição de lote |

## Lógica Desejada (a implementar)

```python
for ratio in range(1, ratio_max_pct + 1):  # ratio = 1, 2, 3, ..., 40 = 1.0x, 1.1x, ..., 1.4x
    n_calls = 1 + ratio                     # ratio=1 → 2 calls, ratio=40 → 41 calls
    pnl_ratio = pnl_base + extra_call_pnl * (n_calls - 1)
    capital_n = preco_compra + premio_put - n_calls * premio_call
    pct_cdi_n = (pnl_ratio / capital_n) / cdi_periodo
    if pct_cdi_n >= premio_risco:
        # Validar range em pontos S ∈ [S₀×0.7, S₀×1.3] (ou ±3σ)
        # Se PnL > 0 em todos os pontos → candidato viável
        return ResultadoCaudaAssincrona(ratio_call=n_calls, ...)
```

## Simulações Pendentes
Rodar com pares reais PETR4/VALE3 para validar quais ratios descobertos gerariam variante (substituir trava `be >= k_3sigma` por validação de range em ±3σ + critério `pct_cdi_ratio ≥ alvo`).

## Arquivos Relevantes
- `src/domain/services/calculadora_cauda_assincrona.py` (157 linhas) — núcleo do cálculo
- `src/ui/desktop/monitor_worker.py:404–485` — `_processar_cauda()` (chamada real)
- `src/domain/services/calculadora_colar_calendario.py:72–417` — calculadora base
- `src/ui/desktop/colar_calendario_dialog.py:493` — filtro de Variante na UI
- `tests/domain/test_calculadora_cauda_assincrona.py` (133 linhas, 13 testes)
- `estudos/collar_calendario_estrutural_calda_assincrona.md` — estudo original

## Próximo Passo
- Validar a simulação **fora do sistema** com a nova lógica.
- Aplicar as correções na `calculadora_cauda_assincrona.py`:
  1. Substituir trava `be >= k_3sigma` por validação de range em ±3σ.
  2. Loop de ratio contínuo (não `int`, mas `n = 1 + ratio/10`).
  3. Somar `pct_cdi` com capital real de cada ratio (não capital_base).
  4. Log de diagnóstico quando `gap ≤ 0` (mostrando `pct_cdi_base`, alvo e motivo de rejeição).
- Replicar para as tabelas Collar Calendário (Já integrada).
