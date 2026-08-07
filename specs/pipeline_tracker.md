# PipelineTracker

Rastreador de pipeline de filtros — coleta métricas de cada estágio do pipeline
de varredura (entrada, saída, rejeitados, tempo) sem afetar a execução.
Usado por todos os use cases de monitor para telemetria e diagnóstico.

## Contrato (Requisitos)

### `PipelineStage` (dataclass)
**Garante:**
1. `nome: str` — nome do estágio ("Filtro Liquidez", "Filtro CDI", etc.).
2. `entrada: int` — número de candidatos que entraram.
3. `saida: int` — número que passaram.
4. `rejeitados: int = 0` — `entrada - saida`.
5. `motivo: str = ""` — descrição do filtro/rejeição.
6. `tempo_s: float = 0.0` — tempo decorrido neste estágio.

### `PipelineTracker(nome_estrategia="")`
**Garante:**
1. `nome_estrategia: str` — identificador da estratégia (ex: "BOX", "SBTH").
2. `stages: list[PipelineStage]` — lista de estágios registrados.
3. `_last_t: float` — timestamp do último `add_stage` (via `time.perf_counter()`).

### `add_stage(nome, entrada, saida, motivo="", tempo_s=None)`
**Garante:**
1. Se `tempo_s is None`, calcula `now - self._last_t`.
2. Atualiza `_last_t = now`.
3. `rejeitados = entrada - saida` (calculado automaticamente).
4. Appends `PipelineStage` à lista.

### `total_entrada -> int`
**Garante:**
1. `stages[0].entrada` se houver stages, senão `0`.

### `total_saida -> int`
**Garante:**
1. `stages[-1].saida` se houver stages, senão `0`.

### `__bool__()`
**Garante:**
1. `len(self.stages) > 0` — permite `if tracker:` para verificar se foi usado.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| logging | `getLogger` | Logger do módulo |
| time | `perf_counter` | Medição de tempo de alta precisão |
| dataclasses | `dataclass` | `PipelineStage` |

**É dependência de:**
- 7 use cases: `monitor_oportunidades.py`, `monitor_vendidas.py`, `monitor_venda_coberta.py`, `monitor_box.py`, `monitor_colares.py`, `monitor_colares_calendario.py`, `monitor_put_ratio.py`
- `monitor_worker.py` — cria trackers e passa para use cases
- `pipeline_dialog.py` — UI de visualização do pipeline
- `calculadora_protecao_cauda.py` — import lazy para tracking de estágios de proteção

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 57 |
| Arquivo | `src/domain/services/pipeline_tracker.py` |
| Última modificação | 2026-06-26 |

## Notas
- 2026-06-26: última modificação (2 commits, 2026-06-24 e 2026-06-26).
- Design não-invasivo: o tracker é um parâmetro opcional nos use cases — se `None`, os filtros operam normalmente sem coleta.
- `rejeitados` é sempre derivado de `entrada - saida` — nunca atribuído diretamente.
- Nenhum teste dedicado para `PipelineTracker` (search em `tests/` não encontrou referências). Testado indiretamente via use cases.
