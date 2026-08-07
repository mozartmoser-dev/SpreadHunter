# criar_data_source

Factory function que instancia o adaptador de market data correto com base na string
de configuração `fonte_market_data` (do banco de parâmetros). Suporta três backends:
Profit RTD (COM), OpenFast (socket TCP) e Mock (dados simulados para teste).

## Contrato (Requisitos)

### `criar_data_source(fonte: str, **kwargs) -> MarketDataSource`
**Garante:**
1. `"openfast"` → `OpenFastSocketAdapter()` + aplica `send_delay_ms` se presente em kwargs.
2. `"mock"` → `MockDataSource(db_path=kwargs.get("db_path"))`.
3. Qualquer outra string (incluindo `"profit"`) → `RTDProfitAdapter()` (default).
   POSSÍVEL COMPORTAMENTO NÃO INTENCIONAL: `fonte="profit"` é o fallback implícito
   do `else` — não há branch explícito. Se houver typo na config (ex: `"proift"`),
   o sistema usa RTD silenciosamente em vez de falhar com erro claro.
   [motivo não documentado, confirmar com o autor].
4. Imports são lazy (dentro da função) — evita carregar módulos COM ou socket antes
   do necessário e previne dependências circulares.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| src.infrastructure.providers.openfast_socket_adapter | `OpenFastSocketAdapter` | Import lazy |
| src.infrastructure.providers.mock_market_data | `MockDataSource` | Import lazy |
| src.infrastructure.providers.rtd_profit_adapter | `RTDProfitAdapter` | Import lazy (fallback) |

**É dependência de:**
- `monitor_worker.py` — instancia o data source no início do worker
- `tests/test_data_source_factory.py` — 6 testes
- `tests/test_field_name_enum.py` — 2 testes

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 12 (factory) / 83 (arquivo total) |
| Arquivo | `src/domain/services/market_data_source.py` |
| Última modificação | 2026-07-28 |

## Notas
- 2026-07-28: última modificação do arquivo (adição de campos ao `FieldName`).
- Imports lazy são essenciais: `RTDProfitAdapter` importa `win32com.client` que exige `CoInitialize()` — carregar no import do módulo quebraria em threads sem COM inicializado.
- A factory não valida `fonte` contra uma lista conhecida — qualquer string não reconhecida cai no RTD. Testes em `test_data_source_factory.py` cobrem `"profit"`, `"openfast"` e fallback com string arbitrária.
