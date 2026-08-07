# CalculadoraBoxSbth

## Propósito

Calculadora híbrida BOX + SBTH para uma única oportunidade (um par de strikes).
Diferente da `CalculadoraVetorizada` (que processa todos os instrumentos de uma vez),
esta calcula detalhadamente um instrumento específico, incluindo classificação
(`1BOX`, `2SBTH`, `3BOXSBTH`, `TP.Op`) e montagem da operação.

Chamada pelo `MonitorOportunidadesUseCase._calcular_oportunidade()` para os pares
que passaram no filtro vetorizado inicial.

## Contrato (Requisitos)

### `calcular(dados: DadosMercado) -> ResultadoBOXSBTH`

**Garante:**
1. Recebe `DadosMercado` com 24 campos do book (preços, volumes, status).
2. **Custo SBTH:** `preco_ativo + premio_put - premio_call` (compra ação + compra PUT + vende CALL).
3. **Custo BOX:** `custo_sbth` + hedge (compra PUT adicional + vende CALL adicional para
   neutralizar o delta da SBTH, criando uma posição delta-neutra).
4. Classificação via bitmask: BOX viável=1, SBTH viável=2, ambos=3 → `"3BOXSBTH"`,
   só BOX → `"1BOX"`, só SBTH → `"2SBTH"`, nenhum → `"TP.Op"`.
5. **Viabilidade:** `pct_cdi ≥ premio_risco` para cada lado individualmente.
6. `_determinar_operacao()` escolhe BOX, SBTH, BOXSBTH, ou NEUTRA baseado
   na classificação e no sinal do lucro.

### `DadosMercado`

DTO com 24 campos: `preco_ativo`, `strike`, `dias`, `premio_put`, `premio_call`,
`qtd_put`, `qtd_call`, `vov_put`, `voc_call`, `status_put`, `status_call`,
`of_venda_*`, `of_compra_*`, `em_leilao`, `vencimento`.

## Dependências

- `src.domain.services.calendario_b3` → `dc_to_du`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`

## Cobertura de Teste

**Status: Parcial (inventory.md).** Testes em `test_fase2.py` (classe `TestCalculadoraBoxSbth`, 10 testes). Sem arquivo dedicado.

## Notas

- 2026-08-07: **BUG CORRIGIDO** — `_determinar_operacao()` para classificação `3BOXSBTH`
  exigia `pct_ganho_box > 0 AND pct_ganho_sbth > 0`; se só um lado tivesse ganho líquido
  positivo, retornava `"NEUTRA"` descartando oportunidade viável.

  **Cenário real:** DTE=1, preco=30, strike=30.68, put_ask=0.65, call_bid=0.48.
  Ambos passam CDI bruto → `"3BOXSBTH"`. SBTH líquido = −0.0075% (B3 custa R$0,032 vs
  ganho R$0,03). BOX líquido = +1.58% (viável). Antes: `"NEUTRA"`. Depois: `"BOX"`.

  **Antes** (`calculadora_box_sbth.py:162`):
  ```python
  if classificacao == "3BOXSBTH" and pct_ganho_box > 0 and pct_ganho_sbth > 0:
      return "BOXSBTH"
  ```

  **Depois** (`calculadora_box_sbth.py:162-168`):
  ```python
  if classificacao == "3BOXSBTH":
      if pct_ganho_box > 0 and pct_ganho_sbth > 0:
          return "BOXSBTH"
      if pct_ganho_box > 0:
          return "BOX"
      if pct_ganho_sbth > 0:
          return "SBTH"
  ```

  Teste de regressão: `test_fase2.py::TestCalculadoraBoxSbth::test_determinar_operacao_3boxsbth_somente_box_viavel`.
