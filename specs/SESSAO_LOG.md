# Sessão 07/08/2026

## Resumo

Geração em lote das 20 specs OpenSpec (módulos 1-20 da fila) no diretório `specs/`, cobrindo
calculadoras de domínio, use cases de monitoramento e repositórios. Auditoria detalhada de 6
módulos críticos: ParametroRepository, CalculadoraProtecaoCauda, CalculadoraCaudaAssincrona,
InstrumentoRepository, CalculadoraColarCalendario, CalculadoraPutRatio. Três bugs reais
encontrados e corrigidos, dois em produção (MonitorPutRatioUseCase e CaudaAssincrona) e um em
código de teste/simulação (PUT ATM). Suíte de 583 testes mantida verde (578 pass, 1 flaky
pré-existente de socket OpenFast).

## Bugs encontrados e corrigidos

1. **Módulo 3 — PUT ATM (teste/simulação):** convenção de dias corridos vs dias úteis em
   Black-Scholes. Corrigido mas sem impacto em produção (código de simulação).

2. **Módulo 6 — CalculadoraCaudaAssincrona:** `bs_put_ref = 0.0` no fallback sem BS do
   `calcular()`. PUT ITM ignorava payoff intrínseco, subestimando proteção na cauda esquerda.
   Corrigido para `max(0, strike_put - preco_ativo)`. Teste `TestPutIntrinsecoSemBS` adicionado.
   Spec: `calculadora_cauda_assincrona.md` Decisão #8.

3. **Módulo 7 — CalculadoraPutRatio (PRODUÇÃO):** `T = dias / 365.0` na linha 138 para
   Black-Scholes. Sistema inteiro padronizou `du/252`: CalculadoraColar (L249),
   CalculadoraColarCalendario (L311-312), CalculadoraCaudaAssincrona (L134). Afetava
   `estimar_iv`, `delta_put` e `sigma_be`. Divergência de 21bp na IV e 0.003 no delta para
   caso típico (dias=45, du=30). Corrigido para `du_val_bs / 252.0`. Teste
   `TestConvencaoTBlackScholes` adicionado (falhava antes, passa depois). Spec:
   `calculadora_put_ratio.md` Decisão #3 (BUG CORRIGIDO).

## Módulos auditados

| # | Arquivo | Status | Bugs |
|---|---------|--------|------|
| 1 | ParametroRepository | ✅ Auditado | — |
| 2 | CalculadoraProtecaoCauda | ✅ Auditado | — |
| 3 | CalculadoraCaudaAssincrona | ✅ Auditado | BUG CORRIGIDO (bs_put_ref) |
| 4 | InstrumentoRepository | ✅ Auditado | — |
| 5 | CalculadoraColarCalendario | ✅ Auditado | — |
| 6 | CalculadoraPutRatio | ✅ Auditado | BUG CORRIGIDO (T=du/252) |

## Pendências para amanhã

- Completar auditoria dos módulos 8-20 restantes
- Atualizar `PENDENCIAS_AMANHA.md`
