# CalculadoraVetorizada

## Propósito

Motor vetorizado de BOX e SBTH que processa TODOS os instrumentos de uma vez com numpy.
Chamado pelo `MonitorOportunidadesUseCase.varrer()` no primeiro estágio do pipeline
(etapa "Geral" do worker). Substitui o loop O(n) por operações vetorizadas O(1) numpy.

Diferente de `CalculadoraBox` e `CalculadoraBoxSbth` (que calculam instrumento por
instrumento), este módulo recebe arrays numpy de todos os instrumentos carregados
e devolve `ResultadoVetorizado` com índices dos pares viáveis + arrays de %CDI.

## Contrato (Requisitos)

### `calcular(...) -> ResultadoVetorizado`

**Garante:**
1. Recebe `preco_ativo`, `of_venda_ativo`, `of_venda_put`, `of_compra_call`, `strike`,
   `dias`, `vov_put_boca`, `voc_call_boca`, `em_leilao` como `np.ndarray`.
2. **Fórmula vetorizada (element-wise):**
    ```
    cdix = (1 + taxa_cdi)^(du/252) - 1
    custo_box = preco_compra_ativo + of_venda_put - of_compra_call
    custo_sbth = preco_compra_ativo + of_venda_put
    pct_cdi_box = (receb_box / custo_box) / cdix
    pct_cdi_sbth = (receb_sbth / custo_sbth) / cdix
    ```
    Onde `preco_compra_ativo = of_venda_ativo` (ask do ativo), `receb_box = of_compra_ativo + of_compra_call`,
    `receb_sbth = of_compra_ativo + of_compra_put`.
3. Filtro de viabilidade: `vov_put_boca ≥ lote_put` E `voc_call_boca ≥ lote_call`.
    `em_leilao` é **identificado visualmente, não descarta** — o filtro de viabilidade não
    usa `em_leilao` como critério de rejeição.
4. `dc_to_du_vetorizado` com `vencimentos=None` — preserva aproximação `DU ≈ DC * 252/365`,
    mesma convenção do cálculo OO anterior. Calendário B3 exato **não** é usado (testes mostraram
    diferenças de classificação na fronteira).
5. Retorna índices viáveis (máscara booleana convertida para índices) e arrays
   de %CDI bruto, líquido (pós-B3), e pós-IR para BOX e SBTH.
6. O cálculo de custos B3 é vetorizado usando a mesma fórmula de
   `CalculadoraBoxSbth` mas aplicada em arrays.

## Dependências

- `numpy` — `np.ndarray`, operações vetorizadas
- `src.domain.services.calendario_b3` → `dc_to_du_vetorizado`
- `src.domain.services.calculadora_custos_b3` → `CalculadoraCustosB3`

## Cobertura de Teste

**Status: 0 testes.** Nenhum arquivo de teste dedicado. Exercitado indiretamente via
`test_fase3.py`/`test_fase4.py` que testam `MonitorOportunidadesUseCase` (que internamente
chama a calculadora vetorizada).
