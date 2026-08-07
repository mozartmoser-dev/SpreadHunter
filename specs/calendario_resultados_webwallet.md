# CalendarioResultadosWebWallet

Cliente HTTP para scraping da agenda de resultados do site webwallet.com.br. Faz parse de tabelas HTML com BeautifulSoup para extrair eventos previstos de divulgação de resultados, ticker e CNPJ.

## Contrato (Requisitos)

### `__init__()`
**Garante:**
1. Sem estado interno relevante (stateless — cada chamada cria nova sessão).

### `buscar_todos() -> list[dict]`
**Garante:**
1. Itera páginas de 1 até `MAX_PAGINAS = 10`.
2. Para cada página, chama `_buscar_pagina`.
3. Se uma página retorna lista vazia, interrompe (assume que não há mais páginas).
4. Retorna lista concatenada de todos os eventos.

### `_buscar_pagina(pagina: int) -> list[dict]`
**Garante:**
1. Monta URL com parâmetros: `TBLPF_TBL_AAGR_DT_PUBLICACAO_FINI` = data de hoje (formato BR) e `TBLPL_TBL_PG` = número da página (se > 1).
2. Faz GET com timeout 15s.
3. Se status != 200, loga warning e retorna `[]`.
4. Delega parse para `_parse_html`.

### `_parse_html(html: str) -> list[dict]`
**Garante:**
1. Localiza `table#TBL tbody`.
2. Itera sobre `<tr>`, extraindo de `<td>`: data (col 0), CNPJ (col 1), ticker/nome (col 2 via `img[alt]` ou `span[data-original-title]`).
3. Ticker é extraído do `alt` da imagem (`"TICKER - Nome Empresa"`) ou do `data-original-title` do span.
4. Fallback: se não encontrou ticker, usa coluna 3 como nome.
5. Data parseada via `_parse_date` (formatos: `%d/%m/%Y`, `%Y-%m-%d`, `%d/%m/%y`).
6. CNPJ limpo via `_limpar_cnpj` (só dígitos).
7. Retorna lista de dicts: `{ativo, cnpj, nome_empresa, data_publicacao, trimestre_referencia: "", tipo_documento: "ITR", tipo_evento: "previsto", fonte: "webwallet"}`.

### `_parse_date(text: str) -> str | None` (static)
**Garante:**
1. Tenta parsear com formatos `%d/%m/%Y`, `%Y-%m-%d`, `%d/%m/%y`.
2. Retorna `date.isoformat()` ou `None`.

### `_limpar_cnpj(text: str) -> str` (static)
**Garante:**
1. Remove tudo que não é dígito (`\D`).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `re` | `re` | Regex para limpeza de CNPJ |
| `datetime` | `date`, `datetime` | Parsing de datas |
| `requests` | `requests` | HTTP client |
| `bs4` | `BeautifulSoup` | Parse HTML |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 118 |
| Última modificação | 2026-07-30 |
| Classes | 1 (`CalendarioResultadosWebwalletProvider`) |

## Notas

- 2026-07-30 — última modificação.
- Scraping de HTML — suscetível a quebras se o site mudar a estrutura da tabela ou classes CSS.
- `tipo_evento` é sempre `"previsto"` (previsão de divulgação). Eventos `"publicado"` vêm da CVM.
- `trimestre_referencia` é sempre string vazia — o site não fornece essa informação no scraping atual.
- O nome do parâmetro `TBLPF_TBL_AAGR_DT_PUBLICACAO_FINI` sugere um framework específico (possivelmente PHP/CodeIgniter com prefixos de tabela).
