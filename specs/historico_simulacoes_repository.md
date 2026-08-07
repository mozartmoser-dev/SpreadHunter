# HistoricoSimulacoesRepository

Repositório para histórico de simulações de proteção de cauda (tabela `historico_simulacoes`). Persiste resultados detalhados de simulações de estratégias com gregos, P&L, zonas EV e metadados de otimização.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `salvar_lote(registros: list[dict]) -> int`
**Garante:**
1. Insere em lote via `executemany` com colunas extensas: `id_chassi`, `estagio`, `ativo`, `preco_ativo`, `strike_call`, `strike_put`, `dte_original`, `iv_call`, `ratio_call`, `ratio_put`, `pnl_cauda_esq`, `pnl_cauda_dir`, `be_esq`, `be_dir`, `pct_cdi`, `qtd_acao`, `premio_call`, `premio_put`, `preco_compra`, `cod_call`, `cod_put`, `vencimento_call`, `vencimento_put`, `dte_put`, `dte_extra`, `iv_put`, `iv_rank_call`, `iv_rank_put`, `net_credito`, `capital_empregado`, `pnl_projetado`, `pct_retorno`, `pct_cdi_liquido`, `custo_b3`, `custo_ir`, `theta_liquido`, `delta_total`, `vega_liquido`, `valor_put_venc_call`, `pop_upside`, `pop_downside`, `score`, `score_iv`, `tipo_estrategia`, `lado_protegido`, `naked_call_frac`, `naked_put_gap`, `strike_protecao_call`, `strike_protecao_put`, `premio_ask_protecao_call`, `premio_ask_protecao_put`, `qtd_protecao_call`, `qtd_protecao_put`, `custo_protecao_call`, `custo_protecao_put`, `custo_protecao_total`, `pnl_liquido_pos_protecao`, `viavel`, `strikes_bwb_call`, `strikes_bwb_put`, `premios_bwb_call`, `premios_bwb_put`, `custo_borboleta_call`, `custo_borboleta_put`, `lotes_bwb_call`, `lotes_bwb_put`, `cod_prot_call`, `cod_prot_put`, `premio_book_call`, `premio_book_put`, `razao_convexidade_call`, `razao_convexidade_put`, `score_ev`, `score_ev_pct`, `zonas_ev_json`, `is_otimizado`.
2. Usa `.get(c)` para cada coluna — campos ausentes no dict são `None`/`NULL`.
3. Retorna `len(registros)`.

### `listar(limite=500) -> list[dict]`
**Garante:**
1. `SELECT * ORDER BY detectado_em DESC LIMIT ?`.

### `listar_por_chassi(id_chassi: str) -> list[dict]`
**Garante:**
1. `SELECT * WHERE id_chassi = ? ORDER BY estagio`.
2. Um "chassi" agrupa múltiplos estágios da mesma simulação (ex: estágio 1 = sem proteção, estágio 2 = com proteção).

### `contar() -> int`
**Garante:**
1. `SELECT COUNT(*)`.

### `limpar() -> int`
**Garante:**
1. `DELETE FROM historico_simulacoes`.

### `exportar_tudo() -> list[dict]`
**Garante:**
1. Delega para `listar(limite=999999)`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 92 (linhas 997-1088 do arquivo) |
| Última modificação | 2026-08-06 |
| Classes | 1 (`HistoricoSimulacoesRepository`) |

## Notas

- 2026-08-06 — mesma data.
- A tabela tem 50+ colunas, refletindo a complexidade das simulações de proteção de cauda.
- Não há upsert — `salvar_lote` faz INSERT simples. Simulações repetidas para o mesmo chassi criam novas linhas (cada execução é um snapshot independente).
- `is_otimizado` indica se a simulação passou pelo otimizador de parâmetros.
- A coluna `zonas_ev_json` armazena dados de Expected Value por zona de preço em JSON.
