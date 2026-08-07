# FieldName

Enum que define os campos de market data disponíveis no sistema. Abstrai as diferenças
de nomenclatura entre Profit RTD (COM) e OpenFast (socket TCP), permitindo que o
`mercado_data_provider.py` e os use cases referenciem campos por nome canônico.

## Contrato (Requisitos)

### `FieldName` (Enum, `auto()`)
**Garante:**
1. Membros:
   - `STRIKE` — preço de exercício (PEX).
   - `LAST_PRICE` — último preço negociado.
   - `BID` — oferta de compra.
   - `ASK` — oferta de venda.
   - `STATUS` — estado do ativo/opção (ex: "NEG", "LEI").
   - `QTD_LAST` — quantidade do último negócio.
   - `VOL_BID` — volume na oferta de compra.
   - `VOL_ASK` — volume na oferta de venda.
   - `BOOK_HEADER` — cabeçalho do book (Profit-only).
   - `HIGH`, `LOW`, `OPEN`, `CLOSE` — OHLC (OpenFast).
   - `VOLUME`, `VOLUME_FIN` — volume (total e financeiro).
   - `VARIATION` — variação percentual.
2. Valores são `auto()` — sem significado semântico; o mapeamento está nos dicionários.

### `PROFIT_FIELD_STR: dict[FieldName, str]`
**Garante:**
1. Mapeia 15 campos para strings do protocolo Profit RTD (ex: `FieldName.BID → "OCP"`).
2. `BOOK_HEADER → "CAB"` — campo específico do Profit (não existe no OpenFast).

### `OPENFAST_FIELD_STR: dict[FieldName, str]`
**Garante:**
1. Mapeia 11 campos para strings do protocolo OpenFast (ex: `FieldName.BID → "BID"`).
2. Não inclui `BOOK_HEADER`, `HIGH`, `LOW`, `VOLUME`, `VOLUME_FIN`.
   POSSÍVEL INCONSISTÊNCIA: `FieldName.HIGH`, `LOW`, `VOLUME`, `VOLUME_FIN` existem no enum
   mas não têm mapeamento em nenhum dos dois dicionários — [confirmar se são campos obsoletos
   ou implementação pendente].

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| enum | `Enum`, `auto` | Classe base + valores automáticos |

**É dependência de:**
- 23 call sites em 15+ arquivos
- `rtd_profit_adapter.py` — usa `FieldName` + `PROFIT_FIELD_STR`
- `openfast_socket_adapter.py` — usa `FieldName` + `OPENFAST_FIELD_STR`
- `mercado_data_provider.py` — usa `FieldName` + `MarketDataSource`
- `mock_market_data.py` — usa `FieldName` + `PROFIT_FIELD_STR`
- Todos os use cases de monitor
- `monitor_worker.py`, `main_window.py`, `export_dialog.py`, `mercado_topbar.py`, `sensibilidade_mercado_widget.py`
- `mpp_use_case.py`
- 4 arquivos de teste (`test_field_name_enum.py`, `test_rtd_profit_adapter.py`, `test_openfast_socket_adapter.py`, `test_mercado_provider_openfast.py`)

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 51 (enum + dicionários) / 83 (arquivo total) |
| Arquivo | `src/domain/services/market_data_source.py` |
| Última modificação | 2026-07-28 |

## Notas
- 2026-07-28: última modificação (adição de campos).
- `FieldName`, `MarketDataSource`, `criar_data_source` e os dicionários de mapeamento coexistem em `market_data_source.py`.
- Testes em `tests/test_field_name_enum.py` cobrem consistência do enum.
- Campos `HIGH`, `LOW`, `VOLUME`, `VOLUME_FIN` não mapeados em nenhum dicionário — POSSÍVEL BUG ou código morto.
