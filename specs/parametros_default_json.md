# parametros_default.json

Arquivo de configuração JSON com o blueprint de parâmetros operacionais do sistema.
Usado como seed na criação do banco (`_seed_parametros_colar` em `database.py`)
e como referência editável pelo usuário para customizar a instalação.

## Contrato (Requisitos)

### Estrutura
**Garante:**
1. Objeto JSON com chave `"parametros"` contendo array de objetos.
2. Cada objeto: `chave`, `valor` (string), `estrategia`, `descricao`.
3. `_comment` no topo explicando o propósito.

### Cobertura de estratégias
**Garante:**
1. 18 estratégias distintas:
   `GERAL`, `COLAR`, `COLLAR_CALENDARIO`, `BOX`, `SBTH`, `BOX_4P`, `BOX_SINTETICO`,
   `VENDA_COBERTA`, `SBTH_VENDIDA`, `VENDIDAS`, `TAXA_COMPRADA`, `PUT_RATIO`,
   `MPP`, `MRE`, `PERFORMANCE`, `PROTECAO_CAUDA`, `RATIOS_OTIMIZADOS`, `IMPORTACAO`,
   `TELEGRAM`, `SOM`.

### Parâmetros críticos (valores divergentes do hardcoded)
**Garante:**
1. JSON vs. hardcoded em `_seed_parametros_colar()` — valores DIFERENTES:
   - `premio_risco_colar`: JSON `"0.85"` vs. hardcoded `"0.7"`.
   - `calendario_strike_diff_max`: JSON `"5.0"` vs. hardcoded `"1"`.
   - `premio_risco_colar_calendario`: JSON `"2.4"` vs. hardcoded `"0.9"`.
   - `taxa_emolumento_pct`: JSON `"0.0003"` vs. hardcoded `"0.00025"`.
   - `taxa_liquidacao_pct`: JSON `"0.0003"` vs. hardcoded `"0.000275"`.
   - `box_premio_risco` (MPP): JSON `"1.5"` vs. hardcoded `"1.08"`.
   - `mpp_peso_profundidade`: JSON `"0.0"` vs. hardcoded `"0.10"`.
   - `mpp_peso_imbalance`: JSON `"0.05"` vs. hardcoded `"0.0"`.
   - `mpp_dte_fator_min`: JSON `"1.0"` vs. hardcoded `"0.60"`.
   - `mre_profundidade_max_pct`: JSON `"0.0"` vs. hardcoded `"0.20"`.
   - `openfast_send_delay_ms`: JSON `"0.0"` vs. hardcoded `"2"`.
   - `perf_carga_inteligente`: JSON `"0.0"` vs. hardcoded `"1"`.
   - `perf_range_min/max`: JSON `"-99.0"/"100.0"` vs. hardcoded `"-70"/"70"`.
   E outros. O JSON vence no seed (é lido primeiro, hardcoded é fallback).
   POSSÍVEL PROBLEMA DE CONSISTÊNCIA: divergência entre JSON e hardcoded pode
   causar comportamentos diferentes dependendo de qual fonte foi usada no seed
   — [confirmar com o autor qual é a fonte autoritativa para cada valor].

2. Parâmetros exclusivos do JSON (não existem no hardcoded):
   - `ex_dividendo_lookback_dias`, `perf_filtro_semanal`, `taxa_cdi`, `premio_risco_box`,
     `premio_risco_sbth`, `premio_box_sintetico_call_itm`, `sbth_qtd_ativo`, `sbth_prof_ativo`,
     `sbth_qtd_put`, `sbth_prof_put`, `box_qtd_ativo`, `box_prof_ativo`, `box_qtd_put`,
     `box_prof_put`, `box_qtd_call`, `box_prof_call`, `basket_*`, `tema_visual`,
     `notif_telegram_enable`, `telegram_bot_token`, `telegram_chat_id`, `taxa_registro_pct`,
     `taxa_iss_pct`, `box_qtd_min`, `box_soh_europeia`, `mpp_iv_*`, `black_list_import`,
     `venda_coberta_dias_minimos`, `som_*`, `vendidas_premio_risco`, `black_list_box4p`,
     `put_ratio_*`, `limite_protecao_pct_rendimento`, `limite_protecao_pct_plato`,
     `limite_protecao_pct_protecao`, `razao_convexidade_max`, `spread_maximo_pct`,
     `taxa_comprada_*`, `box_spread_max_pct`.

## Dependências Diretas (por import — arquivos que leem este JSON)
| Módulo | Uso |
|---|---|
| `src/infrastructure/persistence/database.py` | `_seed_parametros_colar` — seed inicial |
| `src/ui/desktop/parametros_widget.py` | Reset para defaults |
| `scripts/verificar_integridade_params.py` | Validação de consistência |
| `scratch/sync_json.py` | Sincronização JSON ↔ hardcoded |

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 1109 |
| Arquivo | `config/parametros_default.json` |
| Última modificação | 2026-08-07 (hoje) |

## Notas
- 2026-08-07: modificado hoje (adição de `box_spread_max_pct` e outros).
- 2026-08-06, 2026-08-05: modificações recentes (iteração ativa nos parâmetros).
- Divergência JSON vs. hardcoded é conhecida e intencional — o JSON é a fonte "editável pelo usuário", o hardcoded é o fallback seguro de fábrica. Mas a divergência em si não é documentada como decisão explícita.
- AGENTS.md regra #3: "TODO valor de negócio via repo.get_by_chave(). Nunca hardcoded." — o hardcoded em `_seed_parametros_colar` viola esta regra como fallback de seed, mas é tolerado porque só roda no primeiro bootstrap.
