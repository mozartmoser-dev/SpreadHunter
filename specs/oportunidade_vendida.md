# OportunidadeVendida

DTO para oportunidades de estruturas vendidas: BOX Vendido e SBTH Vendida.
Representa a venda de ação + opções, com métricas de rentabilidade e CDI.

## Contrato (Requisitos)

### `OportunidadeVendida` (dataclass, `slots=True`)
**Garante:**
1. `classificacao: str` — campo obrigatório (sem default): `"BOX_VENDIDO"` ou `"SBTH_VENDIDA"`.
2. `recebimento: float` e `viavel: bool` — obrigatórios, sem default.
3. `label_tipo` mapeia `"BOX_VENDIDO"` → `"BOX VENDIDO"`, `"SBTH_VENDIDA"` → `"SBTH VENDIDA"`.
4. `custo_box_display` retorna custo formatado se `custo > 0` e `"BOX" in classificacao`, senão `"-"`.
5. `custo_sbth_display` — análogo para `"SBTH"`.
6. `leilao_display` retorna `"⚠ LEILAO"` se `em_leilao`, senão `""`.
7. Campos de liquidez e custo: `of_compra_put`, `of_venda_call`, `qul_put`, `qul_call`, `custo`, `taxa_aluguel`.
8. Campos de rentabilidade: `pct_ganho`, `pct_cdi`, `pct_ganho_bruto`, `pct_ganho_liquido`, `pct_cdi_bruto`, `pct_cdi_liquido`.
9. `label_detectado` — mesmo padrão `ZoneInfo("America/Sao_Paulo")` dos outros DTOs. Inclui sufixo `label_origem` quando disponível.
10. Campos de timestamp: `ts_ativo_ask`, `ts_ativo_bid`, `ts_origem_ativo`, `idade_origem_ativo` (float|None, default None).
11. `idade_ativo_ask` (property): `time.time() - ts_ativo_ask` se definido.
12. `label_origem` (property): formata `idade_origem_ativo` para diagnóstico.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| dataclasses | `dataclass` | Decorador |
| datetime | `date`, `datetime` | Tipos de dados |
| zoneinfo | `ZoneInfo` | Conversão de timezone (import lazy em `label_detectado`) |

**É dependência de:**
- `src/application/use_cases/monitor_vendidas.py` — cria e popula instâncias
- `src/ui/desktop/vendidas_table_model.py` — tabela de vendidas
- `tests/test_exportar_csv_dtos.py` — 4 testes de exportação CSV

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 99 |
| Arquivo | `src/application/dtos/dtos_vendida.py` |
| Última modificação | 2026-07-29 |

## Notas
- 2026-07-29: refatoração de display properties em lote.
- Duplicação notável: `label_detectado` é idêntico (código copiado) entre `OportunidadeVendida`, `OportunidadeVendaCoberta` e `OportunidadeMonitor` — POSSÍVEL OPORTUNIDADE DE REFACTOR (extrair para mixin ou helper), mas sem urgência [confirmar com o autor].
