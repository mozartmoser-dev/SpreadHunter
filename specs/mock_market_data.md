# MockMarketDataProvider

Provedor sintético de dados de mercado para testes e desenvolvimento. Gera preços plausíveis para pares (CALL, PUT) baseados em um preço de referência, com sobreescrita por instrumento (`set_override`). Inclui `MockDataSource` que implementa a interface duck-typed de `MarketDataSource`.

## Contrato (Requisitos)

### `MockMarketDataProvider.__init__(preco_base=18.0)`
**Garante:**
1. Define `preco_base` como referência para geração sintética.
2. Inicializa dict de overrides vazio.

### `set_override(key: str, dados: dict)`
**Garante:**
1. Permite sobrescrever os dados gerados para uma chave específica (`"ativo|cod_put"`).

### `gerar_dados_para_instrumentos(instrumentos: list) -> dict[str, dict]`
**Garante:**
1. Para cada instrumento, gera um dict com: `preco_ativo`, `strike_rtd`, `of_compra_ativo`, `of_venda_ativo`, `of_compra_put`, `of_venda_put`, `of_compra_call`, `of_venda_call`, `premio_put`, `premio_call`, `vov_put_boca`, `voc_call_boca`, `qul_put`, `qul_call`.
2. Se strike > preco: PUT ITM (prêmio maior), CALL OTM (prêmio menor).
3. Se strike <= preco: PUT OTM, CALL ITM.
4. Prêmios seguem fórmula linear: `premio_put = 0.5 + (strike - preco) * 0.3` para ITM, `0.2` para OTM.
5. Respeita overrides: se a chave existe em `_overrides`, retorna o override em vez de gerar.

### `MockDataSource.__init__(db_path=None)`
**Garante:**
1. Define atributos duck-typed: `disponivel = True`, `suporta_push = False`, `suporta_cab_skip = False`, `is_mock = True`.
2. Instancia `MockMarketDataProvider` com `preco_base=18.0`.
3. Inicializa cache vazio.

### `MockDataSource.registrar_topico(codigo, campo) -> int`
**Garante:**
1. No-op — sempre retorna 0.

### `MockDataSource.registrar_lista(registros) -> int`
**Garante:**
1. No-op — retorna `len(registros)`.

### `MockDataSource.registrar_status(codigo) -> int`
**Garante:**
1. No-op — retorna 0.

### `MockDataSource.ler_campo_cache(codigo, campo) -> float | None`
**Garante:**
1. Busca no cache interno pela chave `"codigo|FIELD_STR"`.

### `MockDataSource.ler_campos(codigo, *campos) -> dict`
**Garante:**
1. Dict comprehension chamando `ler_campo_cache` para cada campo.

### `MockDataSource.ler_status_cache(codigo) -> str`
**Garante:**
1. Sempre retorna `"Aberto"`.

### `MockDataSource.forcar_leitura(codigo, campo) -> float | None`
**Garante:**
1. Delega para `ler_campo_cache`.

### `MockDataSource.refresh(timeout_ms=0) -> dict`
**Garante:**
1. Sempre retorna `{}`.

### `MockDataSource.popular_cache(dados_mercado: dict)`
**Garante:**
1. Preenche o cache interno a partir de um dict no formato `dados_mercado` (mesmo formato retornado por `capturar_dados_mercado`).
2. Mapeia campos do dict para `FieldName` e popula o cache com chaves `"codigo|FIELD_STR"`.
3. Registra `preco_ativo` tanto para o código da opção quanto para o código do ativo.

### Demais métodos (`desconectar`, `reconectar`, `invalidar_cache`)
**Garante:**
1. No-ops com retornos dummy.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `src.application.dtos.dtos` | `OportunidadeMonitor` | Importado mas não usado diretamente nos métodos |
| `src.domain.services.market_data_source` | `FieldName`, `PROFIT_FIELD_STR` | Tradução de campos |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 126 |
| Última modificação | 2026-07-09 |
| Classes | 2 (`MockMarketDataProvider`, `MockDataSource`) |

## Notas

- 2026-07-09 — última modificação.
- `OportunidadeMonitor` é importado mas não usado nos métodos destas classes. Pode ser um leftover de refatoração.
- O `MockDataSource` é detectado pelo `MercadoDataProvider` via `getattr(source, 'is_mock', False)` e ativa o atalho direto que pula todo o pipeline de registro.
- O cache do `MockDataSource` usa `PROFIT_FIELD_STR` para as chaves (mesmo formato do Profit), garantindo compatibilidade com o código downstream.
