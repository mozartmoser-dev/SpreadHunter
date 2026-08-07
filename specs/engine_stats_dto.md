# EngineStatsDTO

## Propósito

DTO que transporta estatísticas de desempenho do motor de monitoramento
(`MonitorWorker`) para a UI (barra de status, indicadores de saúde do sistema).

Fornece métricas de: tempo de scan, consumo de CPU/memória, contagem de
instrumentos monitorados (Onda 1 e Onda 2), status de conexão com a fonte
de market data, e progresso do ciclo de varredura.

## Contrato (Requisitos)

### `EngineStatsDTO(scan_time_ms, cpu_pct, mem_mb, total_instrumentos, monitored_onda1, monitored_onda2, ...)`

**Garante:**
1. `scan_time_ms: int` — duração do último ciclo de scan em milissegundos.
2. `cpu_pct: float` — percentual de CPU usado pelo processo (0-100).
3. `mem_mb: float` — memória usada pelo processo em megabytes.
4. `total_instrumentos: int` — total de instrumentos carregados na grade.
5. `monitored_onda1: int` — instrumentos na Onda 1 (monitoramento de book completo).
6. `monitored_onda2: int` — instrumentos na Onda 2 (monitoramento de manutenção).
7. `threads_count: int` — número de threads ativas (default `1`).
8. `engine_type: str` — tipo do motor de cálculo (default `"NumPy Vectorized"`).
9. `registrado: bool` — se o registro de performance está ativo (default `False`).
10. `progresso_idx: int` — índice de progresso do ciclo atual (default `0`).
11. `dados_stale: bool` — `True` se os dados de mercado estão desatualizados
    (default `False`).
12. `ultimo_refresh_ha_segundos: int` — segundos desde o último refresh bem-sucedido
    da fonte de market data (default `-1`, sentinela para "nunca").
13. `ciclos_sem_dados: int` — número de ciclos consecutivos sem dados novos
    (default `0`).

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass` | Decorador da classe |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 227 (compartilhado com 4 outros DTOs + 1 enum) |
| Classes | 1 dataclass |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Baixa |
| Testes | Não (sem cobertura direta) |

## Notas

- [2026-05-11 via git log] criado. Última modificação: 2026-07-29.
- `ultimo_refresh_ha_segundos: int = -1` — o valor `-1` é sentinela para
  "nunca houve refresh". A UI deve tratar este valor especial ao exibir
  o status de conexão.
- `ciclos_sem_dados` é incrementado pelo `MonitorWorker` a cada ciclo sem
  dados novos — se atingir um limiar (não definido neste DTO), o sistema
  pode disparar reconexão ou alerta.
- Os campos `monitored_onda1`/`monitored_onda2` refletem o pipeline de duas
  ondas do `MercadoDataProvider`: Onda 1 = book completo (assinatura RTD),
  Onda 2 = manutenção periódica de instrumentos que não estão na Onda 1.
- `engine_type: str = "NumPy Vectorized"` — hardcoded no default, mas o
  campo existe para permitir futuros motores de cálculo (ex: GPU, Cython).
