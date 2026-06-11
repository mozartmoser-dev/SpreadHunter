# Plano de Reforma — Spreadhunter

**Data:** 11/06/2026  
**Base:** Auditorias consolidadas de Mimo, Gemini e Qwen  
**Status:** ✅ Concluído

---

## Fase 1 — Correções Críticas Imediatas (sem dependências)

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| 1 | ✅ Adicionar `import logging` + `logger` em `calculadora_colar.py` | `src/domain/services/calculadora_colar.py` | ✅ |
| 2 | ✅ `check_same_thread=False` em `get_connection()` | `src/infrastructure/persistence/database.py` | ✅ |
| 3 | ✅ Guard de iteração (365) em `_proximo_dia_util` | `src/infrastructure/providers/dividendos_statusinvest.py` | ✅ |
| 4 | ✅ Proteger leitura de `_forcar_colar` com mutex | `src/ui/desktop/monitor_worker.py` | ✅ |
| 5 | ✅ Migration de dividendos com transação atômica | `src/infrastructure/persistence/database.py` | ✅ |

## Fase 2 — Thread Safety

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| 6 | ✅ `threading.Lock` em caches de `InstrumentoRepository` e `ParametroRepository` | `src/infrastructure/persistence/repositories/repositories.py` | ✅ |
| 7 | ✅ Thread safety no `RTDProfit` (`threading.Lock`) | `src/infrastructure/providers/rtd_profit.py` | ✅ |
| 8 | ✅ `deleteLater()` + `_tocar_beep()` (QTimer) em `main_window.py` | `src/ui/desktop/main_window.py` | ✅ |
| 9 | ✅ `TelegramService`: invalidar `_notifier` quando parâmetros mudam | `src/infrastructure/notifications/telegram_service.py` | ✅ |

## Fase 3 — Performance e Parametrização

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| 10 | ✅ Connection pooling via `threading.local()` | `src/infrastructure/persistence/database.py` | ✅ |
| 11 | ✅ Batch `_salvar_spread_history` (INSERT + DELETE em lote) | `src/application/use_cases/mpp_use_case.py` | ✅ |
| 12 | ✅ MPP: ler pesos dinâmicos do DB (`_get_param`) em vez de hardcoded | `src/application/use_cases/mpp_use_case.py` | ✅ |
| 13 | ✅ Seed `box_premio_risco`, `mpp_paridade_normalizador`, `mpp_erro_paridade_limiar` no DB | `src/infrastructure/persistence/database.py` | ✅ |
| 14 | ✅ Paginação em `get_historico_completo` (LIMIT 5000) | `src/infrastructure/persistence/repositories/repositories.py` | ✅ |
| 15 | ✅ Remover `calcular_custos()` legado (usa strike) — substituir por `custos_opcao` | `src/domain/services/calculadora_custos_b3.py` | ✅ |

## Fase 4 — Refatoração e Correções de Lógica

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| 16 | ✅ Top-3 em vez de break no pareamento do collar calendário | `src/application/use_cases/monitor_colares_calendario.py` | ✅ |
| 17 | ✅ Parametrizar `box_scan_interval` (remover hardcoded `% 5`) | `src/ui/desktop/monitor_worker.py` | ✅ |
| 18 | ✅ Alinhar fallbacks DB vs código (`dte_call_min`, `dte_extra_max`, `dte_total_max`) | `src/application/use_cases/monitor_colares_calendario.py` | ✅ |
| 19 | ✅ DTE usando `dc_to_du` (já estava correto — usa aproximação dc→du) | `src/domain/services/calculadora_colar.py` | ✅ |
| 20 | ⏳ RTD instances: dialogs não criam RTD próprio (audit incorreto — já usam instância compartilhada via worker) | N/A (já ok) | ⏳ |
| 21 | ✅ `deleteLater()` em QThread workers no `closeEvent` | `src/ui/desktop/main_window.py` | ✅ |
| 22 | ✅ Extrair lógica duplicada de filtros (carga inteligente + background) | `src/infrastructure/providers/mercado_data_provider.py` | ✅ |

## Fase 5 — Housekeeping (Código Morto, Tipos, Estilos)

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| 23 | ✅ Remover `_get_calculadora()` não usado | `src/application/use_cases/monitor_oportunidades.py` | ✅ |
| 24 | ✅ Remover `_calcular_pct_ganho_sbth()` / `_calcular_pct_ganho_box()` não usados | `src/domain/services/calculadora_box_sbth.py` | ✅ |
| 25 | ✅ Remover `_opp_equal()` não usado | `src/ui/desktop/monitor_table_model.py` | ✅ |
| 26 | ✅ Remover `set_dados_mercado()` vazio | `src/ui/desktop/main_window.py` | ✅ |
| 27 | ✅ Remover `ClassificacaoOportunidade` (import morto) | `src/application/use_cases/monitor_oportunidades.py` | ✅ |
| 28 | ✅ Corrigir `import re as re2` redundante | `src/infrastructure/integrations/opcoesnet_client.py`, `colar_dialog.py`, `colar_calendario_dialog.py` | ✅ |
| 29 | ✅ Remover `_colar_cycle = 0` duplicado | `src/ui/desktop/monitor_worker.py` | ✅ |
| 30 | ✅ Corrigir `vencimento: str` para `vencimento: date` em dtos | `src/application/dtos/dtos.py` | ✅ |
| 31 | ✅ Corrigir `_spacer()` anotação `QLabel` → `QFrame` | `src/ui/desktop/export_dialog.py` | ✅ |
| 32 | ✅ Sessões HTTP: `__del__` + close em `OpcoesNetClient` e `MercadoEstruturalProvider` | `src/infrastructure/integrations/opcoesnet_client.py`, `src/infrastructure/providers/mercado_estrutural_provider.py` | ✅ |

## Fase 6 — Melhorias Discutidas (validadas)

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| 33 | ⏳ RefreshData seletivo via TIDs — `refresh_seletivo()` existe mas não é usado | `src/infrastructure/providers/rtd_profit.py` | ⏳ Futuro |
| 34 | ✅ Seed `mpp_persistencia_divisor`, `mpp_persistencia_max_mult`, `mpp_peso_estrutural`, `mpp_peso_instantaneo` no DB | `src/infrastructure/persistence/database.py` | ✅ |
| 35 | ✅ Fallbacks `dte_call_min=25`, `dte_extra_max=120`, `dte_total_max=180` alinhados com DB | `src/application/use_cases/monitor_colares_calendario.py` | ✅ |

---

**Legenda:** ✅ Concluído | 🔧 Em andamento | ⏳ Pendente | ❌ Cancelado
