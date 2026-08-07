# OpcoesNetClient

Cliente HTTP completo para o site opcoes.net.br. Gerencia login com CSRF token, sessão autenticada e fornece múltiplos endpoints: matriz de opções (strike × vencimento), mapeamento MOD (Americano/Europeu), lista de ativos disponíveis, opções via API OptionsChain e histórico de candles com volatilidade.

## Contrato (Requisitos)

### `__init__()`
**Garante:**
1. Inicializa `_session = None`, `_logged_in = False`.
2. Define `_login_cooldown = 30.0` (evita múltiplas tentativas de login em curto intervalo).
3. Carrega credenciais do `.env` via `load_dotenv()` (chamado no import do módulo, linha 19).

### `login(force=False) -> bool`
**Garante:**
1. Se já logado e `not force`, retorna `True` imediatamente.
2. Respeita cooldown de 30s entre tentativas.
3. Se credenciais não configuradas (`.env`), retorna `False`.
4. Faz GET na página de login para extrair CSRF token.
5. Se CSRF token não encontrado, retorna `False`.
6. Faz POST com `CPF`, `Password`, `RememberMe`, `__RequestVerificationToken`.
7. Verifica se o login foi bem-sucedido: se a URL de resposta ainda contém `/login` e o HTML tem campo `CPF`, login falhou (credenciais inválidas).
8. Armazena `_session` e marca `_logged_in = True`.

### `_garantir_csrf() -> str | None`
**Garante:**
1. Se `_csrf_token` existe e tem menos de 300s, retorna do cache.
2. Se não tem sessão, tenta `login()`.
3. Faz GET em `/acoes/estudo-variacao` para extrair novo CSRF token.
4. Atualiza `_csrf_token` e `_csrf_updated_at`.

### `fetch_matriz(ativo, tipo, session=None) -> list[dict]`
**Garante:**
1. Faz GET em `/matriz-opcoes-strike-x-vencimento/{tipo}s/{ativo}` (ex: `calls/PETR4`).
2. Faz parse da tabela HTML: cabeçalho = vencimentos, corpo = strikes × tickers.
3. Para cada célula com link, extrai ticker, strike (da primeira coluna) e vencimento.
4. Retorna lista de `{ticker, strike, vencimento, tipo, ativo}`.
5. Se `session` fornecida, reusa (não fecha). Senão, cria sessão anônima e fecha.

### `fetch_mod_mapping(ativo, session=None) -> dict[str, str]`
**Garante:**
1. Chama API OptionsChain (anônima) para obter MOD de cada opção.
2. Extrai `opt[0]=ticker`, `opt[2]=MOD` para calls e puts.
3. Retorna dict `{ticker: "A"|"E"}`.

### `fetch_available_assets() -> list[str]`
**Garante:**
1. GET em `/opcoes/bovespa`.
2. Tenta extrair do `<select name="IdLista">` com `value="TA"` (Todos Ativos) via atributo `data-acoes`.
3. Fallback: extrai dos `<option>` do `<select name="IdAcao">`.
4. Retorna lista de tickers em uppercase.

### `fetch_all_options(ativo, delay=0.5) -> list[dict]`
**Garante:**
1. Chama API OptionsChain (anônima) — mesmo endpoint do `MercadoEstruturalProvider`, mas parse diferente.
2. Extrai `expiration["dt"]` como vencimento.
3. Para calls e puts: `opt[0]=código numérico`, concatenado com prefixo do ativo (`ativo[:4]`) para formar o ticker.
4. Retorna `{ticker, strike, vencimento, tipo, ativo, mod}`.
5. Inclui séries semanais (W1-W4) — a API OptionsChain retorna todas as séries.

### `get_stock_history(ativo) -> dict | None`
**Garante:**
1. Chama API `QuotesHistoryByAsset` (timeframe=Day) para obter candles históricos.
2. Retorna dict bruto com `data_fields` e `data_rows`.

### `get_stock_history_formatted(ativo, max_days=252) -> list[dict] | None`
**Garante:**
1. Formata o resultado bruto de `get_stock_history` em lista de dicts: `{date, open, high, low, close, change, volume, vol_hist, vol_impl}`.
2. `max_days` controla quantos pregões retornar (default 252 ≈ 12 meses).
3. Mapeia `fields` por nome (indexação dinâmica, não posicional).

### `get_variacao(ativo, ...) -> dict | None`
**Garante:**
1. Requer login (usa `_session` autenticada).
2. Obtém CSRF token via `_garantir_csrf`.
3. Faz POST em `/acoes/dados-estudo-variacao` com parâmetros de referência.
4. Se 401, tenta relogin e re-chama a si mesmo (recursivo).
5. Retorna dict com `data` (bins de variação), `diasCorridos`, `diasComNegociacao`.

### `get_variacao_formatada(ativo, n_sessoes=21) -> dict | None`
**Garante:**
1. Formata o resultado bruto de `get_variacao`.
2. Calcula média ponderada e desvio padrão a partir dos bins de variação.
3. Retorna `{ativo, n_sessoes, intervalo, bins, media_var, desvio_padrao, strikes_pct}` com níveis 1σ e 2σ.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `math` | `math` | `floor` para timestamp |
| `re` | `re` | CSRF extraction, number parsing |
| `time` | `time` | Cooldown, timestamps |
| `urllib.parse` | `urllib.parse` | URL encoding |
| `typing` | `Optional` | Type hints |
| `datetime` | `datetime` | Parsing de datas |
| `requests` | `requests` | HTTP client |
| `bs4` | `BeautifulSoup` | Parse HTML |
| `dotenv` | `load_dotenv` | Carrega `.env` |
| `os` | `os` | `getenv` para credenciais |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 627 |
| Última modificação | 2026-06-30 |
| Classes | 1 (`OpcoesNetClient`) |

## Notas

- 2026-06-30 — última modificação.
- `load_dotenv()` é chamado no nível do módulo (linha 19), não no `__init__`. Isso significa que as credenciais são carregadas uma vez no import, não a cada instância.
- O login é stateful (mantém `_session` entre chamadas). Se a sessão expirar (401), `get_variacao` tenta relogin automático.
- `fetch_all_options` usa `ativo[:4]` como prefixo para formar o ticker. Isso funciona para ações (PETR4 → PETR), mas pode falhar para tickers com menos de 4 letras ou BDRs.
- A API `QuotesHistoryByAsset` requer `Accept: application/json` (linha 406) — sem isso, o servidor pode retornar HTML.
- `get_variacao_formatada` faz uma aproximação estatística dos bins de variação (calcula centro de cada bin e faz média ponderada). A precisão depende da granularidade dos bins retornados pela API.
