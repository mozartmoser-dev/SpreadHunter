# TelegramService

Facade que integra o `TelegramNotifier` com o banco de parâmetros. Lê configuração de token, chat_id e flag de enable da tabela `parametros_operacionais`, gerencia ciclo de vida do notifier e aplica rate-limiting.

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Instancia `ParametroRepository(db_path)`.
2. Inicializa `_notifier = None`.
3. Define `_min_interval_seconds = 3.0` (rate limit da API Telegram) e `_last_sent_time = 0.0`.

### `_load_params() -> dict[str, str]`
**Garante:**
1. Busca `telegram_bot_token`, `telegram_chat_id` e `notif_telegram_enable` do banco.
2. Valores ausentes retornam string vazia.
3. `enable` é forçado para string via `str(valor)`.

### `_build_notifier() -> TelegramNotifier | None`
**Garante:**
1. Se token ou chat_id vazios ou `"0"`, define `_notifier = None` e retorna `None`.
2. Se `_notifier` já existe com mesmos token/chat_id, reusa.
3. Caso contrário, cria novo `TelegramNotifier` e armazena token/chat_id como atributos ad-hoc (`_notifier._token`, `_notifier._chat_id`).

### `is_enabled() -> bool`
**Garante:**
1. Verifica se `enable == 1.0` E token/chat_id não vazios nem `"0"`.

### `invalidar_cache()`
**Garante:**
1. Define `_notifier = None` (força recriação na próxima chamada).

### `send(message: str) -> bool`
**Garante:**
1. Se `is_enabled()` é False, retorna `False`.
2. Rate-limiting: se menos de 3s desde o último envio bem-sucedido, retorna `False` (skip).
3. Constrói notifier via `_build_notifier`.
4. Se notifier não pôde ser construído, retorna `False`.
5. Envia via `notifier.notify(message)`.
6. Se sucesso, atualiza `_last_sent_time`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `src.infrastructure.notifications.telegram_notifier` | `TelegramNotifier` | Envio HTTP |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Leitura de parâmetros |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 85 |
| Última modificação | 2026-06-11 |
| Classes | 1 (`TelegramService`) |

## Notas

- 2026-06-11 — última modificação.
- O rate-limiting de 3s é uma medida de segurança — a API do Telegram tem limite de ~30 mensagens/segundo por bot, mas 3s evita flood acidental durante rajadas de oportunidades.
- `_build_notifier` armazena `_token` e `_chat_id` como atributos ad-hoc no notifier para comparação futura. Isso é um acoplamento frágil (depende de atributos que não fazem parte da interface de `TelegramNotifier`). POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: se `TelegramNotifier` for refatorado e perder esses atributos, a comparação de reuso quebra.
- O parâmetro `notif_telegram_enable` é tratado como float (`1.0` = habilitado). Qualquer outro valor desabilita.
- `_load_params` não faz cache próprio — cada chamada lê do `ParametroRepository` (que tem cache interno).
