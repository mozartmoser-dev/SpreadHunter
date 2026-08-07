# RTDProfitAdapter

Adapter que traduz `FieldName` (enum do domínio) para strings de campo do Profit (`PROFIT_FIELD_STR`), encapsulando `RTDProfit`. Segue a interface implícita de `MarketDataSource` (duck typing — não há interface formal/ABC). Isola o domínio dos detalhes de string do protocolo RTD.

## Contrato (Requisitos)

### `__init__()`
**Garante:**
1. Instancia `RTDProfit()` internamente.
2. Define atributos de classe: `suporta_push = False`, `suporta_cab_skip = True`.

### `disponivel` (property) -> bool
**Garante:**
1. Delega para `self._rtd.disponivel`.

### `_resolver(campo: FieldName | str) -> str`
**Garante:**
1. Se `campo` é `FieldName`, faz lookup em `PROFIT_FIELD_STR` (retorna string vazia se não encontrado).
2. Se `campo` é `str`, retorna a própria string (pass-through).

### `registrar_topico(codigo: str, campo: FieldName) -> int`
**Garante:**
1. Traduz `campo` via `_resolver` e delega para `self._rtd.registrar_topico(codigo, campo_str)`.

### `registrar_lista(registros: list[tuple[str, FieldName]]) -> int`
**Garante:**
1. Itera sobre a lista de `(codigo, FieldName)`, chamando `registrar_topico` para cada.
2. Insere `time.sleep(0.001)` a cada 10 registros para não sobrecarregar o COM.
3. Retorna contagem de registros bem-sucedidos.

### `registrar_status(codigo: str) -> int`
**Garante:**
1. Delega diretamente para `self._rtd.registrar_status(codigo)`.

### `ler_campo_cache(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Traduz `campo` e delega para `self._rtd.ler_campo_cache`.

### `ler_campos(codigo: str, *campos: FieldName) -> dict[FieldName, float | None]`
**Garante:**
1. Lê múltiplos campos de uma vez, retornando dict `{FieldName: valor}`.
2. Cada campo é lido via `ler_campo_cache` (uma chamada COM por campo — não é batch real).

### `ler_status_cache(codigo: str) -> str`
**Garante:**
1. Delega diretamente para `self._rtd.ler_status_cache`.

### `forcar_leitura(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Traduz `campo` e delega para `self._rtd.forcar_leitura`.

### `refresh(timeout_ms: int = 0) -> dict[str, object]`
**Garante:**
1. Delega diretamente para `self._rtd.refresh(timeout_ms)`.

### `reconectar() -> bool`
**Garante:**
1. Delega diretamente para `self._rtd.reconectar()`.

### `invalidar_cache(codigo: str, campo: FieldName)`
**Garante:**
1. Traduz `campo` e delega para `self._rtd.invalidar_cache`.

### `desconectar()`
**Garante:**
1. Delega diretamente para `self._rtd.desconectar()`.

### `get_ts_campo(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Sempre retorna `None` — RTD Profit não fornece timestamp por campo.

### `get_idade_campo(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Sempre retorna `None` — RTD Profit não fornece idade de campo.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `time` | `time` | Delay entre lotes em `registrar_lista` |
| `src.domain.services.market_data_source` | `FieldName`, `PROFIT_FIELD_STR` | Tradução FieldName → str |
| `src.infrastructure.providers.rtd_profit` | `RTDProfit` | Cliente COM encapsulado |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 71 |
| Última modificação | 2026-08-06 |
| Classes | 1 (`RTDProfitAdapter`) |

## Notas

- 2026-08-06 — última modificação (adição de `desconectar()`).
- `registrar_lista` não faz batch real — chama `registrar_topico` individualmente com sleep a cada 10. O contraste com `OpenFastSocketAdapter.registrar_lista` (que envia tudo em uma string com `\n`) é deliberado: o COM do Profit não suporta batch nativo.
- Duck typing: não implementa `ABC`/`Protocol` formal. A interface é verificada em runtime via `getattr(source, 'suporta_push', False)` etc.
- `get_ts_campo` e `get_idade_campo` retornam `None` porque o RTD Profit não fornece metadados de timestamp.
