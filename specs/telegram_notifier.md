# TelegramNotifier

Cliente HTTP simples para envio de mensagens via API do Telegram (método `sendMessage`). Sem estado além de token e chat_id. Suporte a formatação HTML.

## Contrato (Requisitos)

### `__init__(token: str, chat_id: str)`
**Garante:**
1. Armazena `token` e `chat_id`.
2. Monta `api_url = f"https://api.telegram.org/bot{token}/sendMessage"`.

### `is_configured() -> bool`
**Garante:**
1. Retorna `True` se ambos `token` e `chat_id` são truthy (não vazios).

### `notify(message: str) -> bool`
**Garante:**
1. Se não configurado, loga warning e retorna `False`.
2. Envia POST com payload JSON: `{chat_id, text, parse_mode: "HTML", disable_web_page_preview: True}`.
3. Timeout de 10s.
4. Verifica `resp.json()["ok"]` — se `False`, loga erro e retorna `False`.
5. Em caso de exceção, loga exception completa e retorna `False`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `requests` | `requests` | HTTP client |
| `typing` | `Optional` | Type hints |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 38 |
| Última modificação | 2026-05-19 |
| Classes | 1 (`TelegramNotifier`) |

## Notas

- 2026-05-19 — última modificação.
- Módulo mais simples do sistema — 38 linhas, sem lógica condicional complexa.
- `parse_mode: "HTML"` permite tags HTML na mensagem (`<b>`, `<i>`, `<a>`, etc.).
- `disable_web_page_preview: True` evita previews de links nas mensagens.
- Não há rate-limiting interno — o controle de throttle é feito pelo `TelegramService` que encapsula este notifier.
