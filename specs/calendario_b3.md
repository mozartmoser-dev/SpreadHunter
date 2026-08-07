# CalendarioB3

Módulo de calendário de dias úteis da B3. Fornece funções para conversão de dias
corridos (DC) para dias úteis (DU), frações de ano (252 DU, 365 DC), e verificação
de feriados. Usa `numpy.busdaycalendar` como engine, com fallback aproximado quando
o cálculo exato falha.

## Contrato (Requisitos)

### Constantes e estado global
**Garante:**
1. `FERIADOS_B3_PADRAO: list[str]` — 40 feriados de 2024-2026 em `YYYY-MM-DD`.
2. `B3_CALENDAR: np.busdaycalendar` — calendário NumPy construído a partir da lista.
3. `_feriados_atuais: list[str]` — lista mutável (começa como cópia de `FERIADOS_B3_PADRAO`).
4. `_B3_CALENDAR` — variável interna; `B3_CALENDAR` é o alias público.

### `atualizar_calendario(feriados: list[str])`
**Garante:**
1. Substitui `_feriados_atuais` pela nova lista ordenada.
2. Reconstrói `B3_CALENDAR`.

### `carregar_do_banco(db_path: str | None = None)`
**Garante:**
1. Lê feriados da tabela `feriados_b3` via `FeriadoB3Repository`.
2. Se houver registros, chama `atualizar_calendario(feriados)`.
3. Se o banco estiver vazio ou der erro, mantém os feriados padrão (lista hardcoded).
4. Exceções são silenciosamente ignoradas (`except Exception: pass`).

### `dc_to_du_aproximado(dias_corridos: int) -> int`
**Garante:**
1. `dias_corridos <= 0` → `0`.
2. Aproximação: `round(dias_corridos * 252 / 365)`, mínimo `1`.

### `dc_to_du_exato(data_inicio: date, data_fim: date) -> int`
**Garante:**
1. `data_inicio >= data_fim` → `0`.
2. `np.busday_count(data_inicio, data_fim, busdaycal=_B3_CALENDAR)`.
3. Se `ValueError` (ex: data fora do range do calendário), fallback para `dc_to_du_aproximado()`.

### `dc_to_du_vetorizado(data_inicio: date, vencimentos: np.ndarray) -> np.ndarray`
**Garante:**
1. `len(vencimentos) == 0` → array vazio de int.
2. `np.busday_count` vetorizado contra `B3_CALENDAR` (alias público).
3. `np.maximum(du, 0)` para evitar contagens negativas.
4. Se `ValueError`, retorna array de zeros.

### `dc_to_du(data_inicio, data_fim, dias_corridos=0) -> int`
**Garante:**
1. Se ambas as datas fornecidas → `dc_to_du_exato()`.
2. Caso contrário → `dc_to_du_aproximado(dias_corridos)`.

### `frac_du(dias_uteis: int) -> float`
**Garante:**
1. `dias_uteis <= 0` → `0.0`.
2. `dias_uteis / 252` (fração do ano em dias úteis).

### `frac_dc(dias_corridos: int) -> float`
**Garante:**
1. `dias_corridos <= 0` → `0.0`.
2. `dias_corridos / 365` (fração do ano em dias corridos).

### `eh_feriado(dt: date) -> bool`
**Garante:**
1. `dt.isoformat() in _feriados_atuais`.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| datetime | `date` | Tipo |
| numpy | `np` | `busdaycalendar`, `busday_count`, array |
| src.infrastructure.persistence.repositories.repositories | `FeriadoB3Repository` | Import lazy em `carregar_do_banco` |

**É dependência de:**
- 31 call sites em 20+ arquivos — um dos módulos mais referenciados do sistema
- Todas as calculadoras (`calculadora_box.py`, `calculadora_box_sbth.py`, `calculadora_colar.py`, `calculadora_colar_calendario.py`, `calculadora_vetorizada.py`, `calculadora_put_ratio.py`, `calculadora_cauda_assincrona.py`)
- Todos os use cases de monitor (`monitor_oportunidades.py`, `monitor_vendidas.py`, `monitor_venda_coberta.py`, `monitor_box.py`, `monitor_colares.py`, `monitor_colares_calendario.py`, `monitor_put_ratio.py`, `mpp_use_case.py`)
- `monitor_worker.py`, `main_window.py`, `bootstrap.py`
- Vários dialogs UI (`colar_dialog.py`, `colar_calendario_dialog.py`, `calculadoras_dialog.py`, `feriados_dialog.py`, `estudos_calendario_dialog.py`, `sensibilidade_mercado_widget.py`)
- Scripts de simulação (`.opencode/skills/spreadhunter/sim_*.py`, `scripts/simulador_gregas.py`, `scripts/simular_protecao_cauda.py`)
- `src/infrastructure/providers/dividendos_statusinvest.py` (usa `_feriados_atuais` interno — POSSÍVEL ACOPLAMENTO INDEVIDO)

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 94 |
| Arquivo | `src/domain/services/calendario_b3.py` |
| Última modificação | 2026-06-17 |

## Notas
- 2026-06-17: última modificação.
- Feriados hardcoded para 2024-2026 — expiram. O banco (`feriados_b3`) é a fonte autoritativa em produção (carregado via `carregar_do_banco()` no `bootstrap`).
- `dc_to_du_vetorizado` usa `B3_CALENDAR` (alias público), enquanto `dc_to_du_exato` usa `_B3_CALENDAR` (privado). Ambos apontam para o mesmo objeto — POSSÍVEL INCONSISTÊNCIA caso um seja reconstruído sem o outro.
- `dividendos_statusinvest.py` acessa `_feriados_atuais` diretamente (variável privada) — violação de encapsulamento.
- `carregar_do_banco` silencia todas as exceções com `except Exception: pass` — pode esconder erros de schema.
