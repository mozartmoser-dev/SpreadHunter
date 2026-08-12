# OportunidadeVendaCoberta

DTO para oportunidades de Venda Coberta (covered call). Representa uma CALL vendida
contra posição no ativo, com métricas de rentabilidade bruta, líquida e comparação CDI.

## Contrato (Requisitos)

### `OportunidadeVendaCoberta` (dataclass, `slots=True`)
**Garante:**
1. Campos obrigatórios: `ativo`, `strike`, `vencimento`, `dias`, `cod_put`, `cod_call`, `tipo_opcao`.
2. `classificacao` fixado como `"VENDA_COBERTA"` — nunca varia.
3. `label_tipo` distingue `"COMPRADA"` (se `classificacao == "TAXA_COMPRADA"`) ou `"VENDIDA"` (default).
4. `label_detectado` converte UTC → America/Sao_Paulo (via `zoneinfo`), igual ao `OportunidadeMonitor`.
5. `custo_box_display` e `custo_sbth_display` retornam `"-"` fixo — venda coberta não usa essas métricas.
   POSSÍVEL DUPLICIDADE: essas properties existem para compatibilidade com `OportunidadeMonitor` na tabela genérica,
   mas sempre retornam placeholder — [motivo não documentado, confirmar com o autor].
6. `ganho_display`, `ganho_bruto_display`, `ganho_liq_display` formatam `pct_ganho * 100` como percentual.
7. Campos de liquidez: `of_compra_put`, `of_venda_call`, `qul_put`, `qul_call`, `money_put`, `money_call`.
8. Campos de custo e IR: `custo`, `taxa_aluguel`, `pct_ganho_bruto`, `pct_ganho_liquido`, `pct_cdi_bruto`, `pct_cdi_liquido`.
9. Campos de timestamp: `ts_ativo_ask`, `ts_ativo_bid`, `ts_origem_ativo`, `idade_origem_ativo` (float|None, default None).
10. `idade_ativo_ask` (property): `time.time() - ts_ativo_ask` se definido.
11. `label_origem` (property): formata `idade_origem_ativo` para diagnóstico.
12. `label_detectado` — mesmo padrão dos outros DTOs, com sufixos de origem e idade do ativo.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| dataclasses | `dataclass` | Decorador |
| datetime | `date`, `datetime` | Tipos de dados |
| zoneinfo | `ZoneInfo` | Conversão de timezone (import lazy em `label_detectado`) |

**É dependência de:**
- `src/application/use_cases/monitor_venda_coberta.py` — cria instâncias
- `src/ui/desktop/venda_coberta_table_model.py` — exibe na tabela

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 99 |
| Arquivo | `src/application/dtos/dtos_venda_coberta.py` |
| Última modificação | 2026-07-29 |

## Notas
- 2026-07-29: última modificação em lote com outros DTOs (refatoração de display properties).
- 2026-07-24: data intermediária sugere adição de campos de rentabilidade líquida/bruta.
- `custo_sbth_display` e `custo_box_display` retornam `"-"` fixo — POSSÍVEL DEAD CODE herdado de interface comum com `OportunidadeMonitor`.
