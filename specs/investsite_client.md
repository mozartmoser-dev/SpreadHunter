# InvestSiteClient

Cliente HTTP para scraping de taxas de aluguel de ações do site investsite.com.br. Faz parse de HTML para extrair taxa atual, média 7 dias e média 28 dias de aluguel para um ativo.

## Contrato (Requisitos)

### `__init__(timeout_seconds=10)`
**Garante:**
1. Armazena timeout para requisições HTTP.

### `fetch_taxa_aluguel(ativo: str) -> dict | None`
**Garante:**
1. Monta URL `https://www.investsite.com.br/graficos_aluguel_registro.php?cod_negociacao={ATIVO}`.
2. Faz GET com User-Agent de navegador.
3. Se status != 200, loga warning e retorna `None`.
4. Força encoding `utf-8` na resposta.
5. Delega parse para `parse_html`.

### `parse_html(html_content: str, ativo: str) -> dict | None`
**Garante:**
1. Localiza `<section id="resumo">`.
2. Extrai via regex do texto da seção:
   - Data de referência: `atualmente (DD/MM/AAAA)`
   - Taxa atual: `taxa média anualizada de X%`
   - Taxa 7d: `últimos 7 dias foi de X%`
   - Taxa 28d: `últimos 28 dias foi de X%`
3. Se qualquer campo ausente, retorna `None`.
4. Retorna `{ativo, data, taxa_atual, taxa_7d, taxa_28d}` com data como `date` e taxas como `float`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `re` | `re` | Regex para parse do texto |
| `requests` | `requests` | HTTP client |
| `bs4` | `BeautifulSoup` | Parse HTML |
| `datetime` | `date`, `datetime` | Parsing de datas |
| `logging` | `logging` | Logger |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 62 |
| Última modificação | 2026-07-05 |
| Classes | 1 (`InvestSiteClient`) |

## Notas

- 2026-07-05 — última modificação.
- Scraping frágil: depende de regex específicos no texto da seção `#resumo`. Se o site mudar o texto ou estrutura, o parse falha silenciosamente (retorna `None`).
- O encoding é forçado para `utf-8` (linha 27: `response.encoding = 'utf-8'`). Se o site servir em outro encoding, pode haver perda de caracteres (ex: acentos).
- `parse_html` é público para permitir teste unitário com HTML mockado.
