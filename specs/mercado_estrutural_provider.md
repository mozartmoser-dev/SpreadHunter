# MercadoEstruturalProvider

Cliente HTTP para a API pública do opcoes.net.br (OptionsChain). Busca dados estruturais de opções (strike, vencimento, tipo, MOD, gregos, volume) para um ativo, com batch e rate-limiting. Usado pelo importador `importflash.py` como fonte de dados de mercado estrutural.

## Contrato (Requisitos)

### `__init__()`
**Garante:**
1. Cria `requests.Session` com headers de navegador (User-Agent, Accept, Accept-Language, Referer).

### `fetch_options_data(ativo: str) -> list[dict]`
**Garante:**
1. Monta URL com parâmetros `OptionsChain` + `LastQuotesInfo` e timestamp `z = floor(time.time() / 10)` (cache-busting a cada 10 segundos).
2. Faz GET com timeout de 30s.
3. Se `data["success"]` é False, loga warning e retorna `[]`.
4. Itera sobre `expirations`, filtrando vencimentos > hoje.
5. Para cada expiration, extrai calls e puts via `_parse_option`.
6. Retorna lista de dicts com campos: `opcao`, `strike`, `tipo`, `vencimento`, `ativo`, `ultimo_preco`, `num_negocios`, `volume_financeiro`, `titulares`, `lancadores`, `iv`, `delta`, `gamma`, `mod`.

### `_parse_option(opt: list, tipo: str, ativo: str, vencimento: date) -> dict | None`
**Garante:**
1. Verifica `opt[0]` não vazio (código da opção).
2. Extrai campos por índice fixo: `opt[0]=código`, `opt[2]=MOD`, `opt[3]=strike`, `opt[6]=último preço`, `opt[9]=nº negócios`, `opt[10]=volume financeiro`, `opt[15]=titulares`, `opt[16]=lançadores`, `opt[17]=IV`, `opt[18]=delta`, `opt[19]=gamma`.
3. Se qualquer campo falhar no parse (ValueError, IndexError, TypeError), retorna None (linha ignorada).

### `fetch_all_whitelist(ativos: list[str]) -> dict[str, list[dict] | None]`
**Garante:**
1. Processa ativos em batches de `BATCH_SIZE = 5`.
2. Entre batches, dorme `BATCH_INTERVAL = 2.0` segundos (rate-limiting).
3. Se um ativo falha, armazena `None` para ele (não interrompe o processo).
4. Retorna dict `{ativo: [opções]}`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `math` | `math` | `floor` para timestamp |
| `time` | `time` | Timestamp + sleep entre batches |
| `urllib.parse` | `urllib.parse` | URL encoding |
| `datetime` | `date`, `datetime` | Parsing de datas |
| `requests` | `requests` | HTTP client |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 112 |
| Última modificação | 2026-06-11 |
| Classes | 1 (`MercadoEstruturalProvider`) |

## Notas

- 2026-06-11 — última modificação.
- A API usada é a pública do opcoes.net.br (não requer login). O parâmetro `z = floor(time.time() / 10)` é um cache-buster que muda a cada 10 segundos.
- Os índices do array `opt` são fixos e dependem do formato da API OptionsChain. Se a API mudar a ordem das colunas, o parse quebra silenciosamente (retorna None, não lança exceção).
- `_parse_option` aceita `ValueError`, `IndexError` e `TypeError` — qualquer campo malformado na linha faz a opção inteira ser ignorada.
- `fetch_all_whitelist` faz rate-limiting com 2s entre batches de 5 ativos. Para 100 ativos, isso leva ~40 segundos só em sleeps.
