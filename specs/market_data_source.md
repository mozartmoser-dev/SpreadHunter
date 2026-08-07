# MarketDataSource

Protocolo (`typing.Protocol`, `@runtime_checkable`) que define a interface de qualquer
fonte de market data no sistema. Três implementações concretas: `RTDProfitAdapter` (COM),
`OpenFastSocketAdapter` (socket TCP) e `MockDataSource` (testes).

## Contrato (Requisitos)

### `MarketDataSource` (Protocol, `@runtime_checkable`)
**Garante:**
1. Atributos obrigatórios:
   - `disponivel: bool` — se a fonte está conectada e operacional.
   - `suporta_push: bool` — se suporta notificações push (Profit) vs. polling (OpenFast).
   - `suporta_cab_skip: bool` — se o protocolo tem cabeçalho de book que precisa ser pulado.
2. Métodos obrigatórios (assinatura Protocol):
   - `registrar_topico(codigo: str, campo: FieldName) -> int` — registra subscrição a um campo.
   - `registrar_lista(registros: list[tuple[str, FieldName]]) -> int` — registro em lote.
   - `registrar_status(codigo: str) -> int` — registra apenas status (sem book).
   - `ler_campo_cache(codigo, campo) -> float | None` — leitura do cache local.
   - `ler_campos(codigo, *campos) -> dict[FieldName, float | None]` — leitura múltipla.
   - `ler_status_cache(codigo: str) -> str` — leitura do status.
   - `forcar_leitura(codigo, campo) -> float | None` — força refresh síncrono.
   - `refresh(timeout_ms=0) -> dict[str, object]` — dispara atualização.
   - `desconectar()` — encerra conexão.
   - `reconectar() -> bool` — reconecta, retorna sucesso.
   - `invalidar_cache(codigo, campo)` — invalida entrada do cache.
3. `@runtime_checkable` — permite `isinstance(obj, MarketDataSource)` em runtime,
   mas verifica apenas atributos (não assinaturas de métodos).

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| typing | `Protocol`, `runtime_checkable` | Definição do protocolo |
| enum | `Enum`, `auto` | `FieldName` — usado nas assinaturas (no mesmo arquivo) |

**É dependência de:**
- `mercado_data_provider.py` — importa `MarketDataSource` como type hint
- `rtd_profit_adapter.py`, `openfast_socket_adapter.py`, `mock_market_data.py` — implementam o protocolo

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 17 (protocol) / 83 (arquivo total) |
| Arquivo | `src/domain/services/market_data_source.py` |
| Última modificação | 2026-07-28 |

## Notas
- Protocolo com `@runtime_checkable` — permite `isinstance()` mas não verifica assinaturas de métodos em runtime (só atributos). Isso significa que `isinstance(obj, MarketDataSource)` pode retornar `True` para um objeto que tem os atributos mas métodos com assinaturas erradas — POSSÍVEL FALSA VERIFICAÇÃO.
- `MarketDataSource`, `FieldName`, `criar_data_source` e dicionários de mapeamento coexistem no mesmo arquivo `market_data_source.py`.
