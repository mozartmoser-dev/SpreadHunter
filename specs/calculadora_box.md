# CalculadoraBox

## Propósito

Calculadora de Box Spread de 4 pernas — a estratégia de renda fixa sintética que combina
compra e venda de CALL e PUT em dois strikes diferentes para travar um lucro conhecido
(short box) ou custo conhecido (long box). A fórmula central é `lucro = clr - distancia`
para short box, onde `clr` é o crédito líquido recebido e `distancia = K2 - K1`.

## Contrato (Requisitos)

### `calcular(...) -> ResultadoBox | None` (short box)

**Garante:**
1. Retorna `None` se: `K1 ≥ K2`, `dias ≤ 0`, qualquer `bid/ask ≤ 0`, `clr ≤ 0`,
   ou profundidade insuficiente.
2. **Crédito líquido recebido (CLR):**
   ```
   clr = (bid_call_k1 + bid_put_k2) - (ask_put_k1 + ask_call_k2)
   ```
   Comprar CALL K1 + PUT K2 (vender ATM), vender PUT K1 + CALL K2 (comprar OTM).
   `bid` = você recebe, `ask` = você paga. Consistente com a regra #6 do AGENTS.md.
3. **Lucro:** `lucro = clr * qtd - (K2 - K1) * qtd` — short box, não inverter.
4. Viabilidade: `pct_cdi_bruto ≥ premio_risco`.
5. Valida MOD da CALL K1: se `soh_europeia=True` e `mod_call_k1 != "E"`, rejeita.

### `calcular_long(...) -> ResultadoBox | None` (long box)

**Garante:**
1. **Débito:** `debito = (ask_call_k1 + ask_put_k2) - (bid_put_k1 + bid_call_k2)`.
2. Exige `debito > 0`.
3. **Lucro:** `lucro = (K2 - K1) * qtd - debito * qtd` — inverte a fórmula do short box.

## Dependências

- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`

## Cobertura de Teste

**Status: Parcial (inventory.md).** Testes embutidos em `test_fase2.py` (classe `TestCalculadoraBoxSbth`, 11 testes). Sem arquivo de teste dedicado.
