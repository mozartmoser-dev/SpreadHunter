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

**Status: Parcial (inventory.md).** Testes embutidos em `test_fase2.py` (classe `TestCalculadoraBoxSbth`). Sem arquivo dedicado.
