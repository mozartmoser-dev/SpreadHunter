# DividendosStatusInvest

Cliente HTTP para scraping de proventos (dividendos, JCP, etc.) do site statusinvest.com.br. Faz parse de tabelas HTML para extrair tipo, data-com, data de pagamento e valor por ativo.

## Contrato (Requisitos)

### `buscar_proventos(ticker: str) -> list[dict]`
**Garante:**
1. Faz GET para `https://statusinvest.com.br/acoes/{ticker}` com timeout 15s.
2. Se status != 200, loga warning e retorna `[]`.
3. Localiza a primeira `<table>` do HTML e extrai linhas (pula o cabeçalho).
4. Para cada linha com >= 4 colunas, extrai: `tipo` (col 0), `data_com` (col 1), `data_pagamento` (col 2), `valor` (col 3).
5. `data_com` e `data_pagamento` parseados via `_parse_date` (formato `%d/%m/%Y`).
6. `data_ex` calculada como próximo dia útil após `data_com` via `_proximo_dia_util`.
7. `valor` parseado via `_parse_valor` (formato brasileiro: `1.234,56`).
8. Retorna lista de dicts: `{ativo, tipo, data_com, data_ex, data_pagamento, valor, fonte: "statusinvest"}`.

### `_proximo_dia_util(data_str) -> str | None` (static)
**Garante:**
1. Se `data_str` é `None`, retorna `None`.
2. Tenta carregar feriados via `calendario_b3._feriados_atuais`. Se falhar, assume sem feriados.
3. Avança dias até encontrar um dia útil (seg-sex, não feriado), limite de 365 dias.
4. Retorna `date.isoformat()`.

### `_parse_date(date_str) -> str | None` (static)
**Garante:**
1. Se vazio ou `"-"`, retorna `None`.
2. Parseia `%d/%m/%Y` e retorna `"%Y-%m-%d"`.

### `_parse_valor(valor_str) -> float | None` (static)
**Garante:**
1. Se vazio, retorna `None`.
2. Remove `.` (separador de milhar) e substitui `,` por `.` (decimal).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `requests` | `requests` | HTTP client |
| `bs4` | `BeautifulSoup` | Parse HTML |
| `datetime` | `datetime`, `date`, `timedelta` | Manipulação de datas |
| `src.domain.services.calendario_b3` (runtime) | `_feriados_atuais` | Cálculo de próximo dia útil |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 99 |
| Última modificação | 2026-06-11 |
| Classes | 1 (`DividendosStatusInvestProvider`) |

## Notas

- 2026-06-11 — última modificação.
- Scraping de HTML — suscetível a quebras se o site do StatusInvest mudar a estrutura.
- A importação de `calendario_b3._feriados_atuais` é feita dentro de `_proximo_dia_util` (lazy) com try/except — se falhar, assume que não há feriados (cálculo impreciso mas funcional).
- `data_ex` é calculada como próximo dia útil após `data_com`. Na B3, data-ex é D+1 da data-com, ajustado para dia útil. Esta aproximação é razoável mas pode divergir em casos de feriados não cadastrados.
- Apenas a primeira tabela é usada. Se o StatusInvest adicionar tabelas antes da de proventos, o scraping quebra.
