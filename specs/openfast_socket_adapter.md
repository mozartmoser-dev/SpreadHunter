# OpenFastSocketAdapter

Adapter de socket TCP para o protocolo OpenFast (servidor local na porta 557). Push-based: uma thread leitora (`daemon`) recebe atualizações em tempo real via socket e popula o cache. Suporta reconexão com re-registro de tópicos pendentes e profiling interno de performance.

## Contrato (Requisitos)

### `__init__(host="127.0.0.1", port=557, send_delay_s=0.0)`
**Garante:**
1. Configura socket TCP com `TCP_NODELAY`, buffer de recepção 256KB, buffer de envio 256KB.
2. Handshake: envia `"OPENFAST\n"`, espera linha `version` em até 5s.
3. Se handshake falhar com "mais de uma conex" (servidor ocupado), fecha socket e mantém `_conectado = False`.
4. Inicia thread leitora daemon (`_thread_leitora`).
5. Inicializa atributos de profiling para logging periódico (a cada 30s).

### `disponivel` (property) -> bool
**Garante:**
1. `True` se conectado E o último SYN foi recebido há menos de 20 segundos.
2. O servidor OpenFast envia `SYN` periódico como heartbeat; ausência > 20s indica desconexão.

### `set_send_delay(delay_ms: int)`
**Garante:**
1. Converte ms para segundos e armazena em `_send_delay_s` (mínimo 0.0).

### `registrar_topico(codigo: str, campo: FieldName) -> int`
**Garante:**
1. Traduz `FieldName` via `OPENFAST_FIELD_STR`.
2. Envia comando `on<SEP>SQT<SEP>CODIGO<SEP>CAMPO` via socket.
3. Registra a subscription em `_subscriptions` para re-registro em caso de reconexão.
4. Retorna `0` (sucesso) ou `-1` (campo não mapeado).

### `registrar_lista(registros: list[tuple[str, FieldName]]) -> int`
**Garante:**
1. Monta todas as linhas de subscription e envia em uma única string com `\n` como separador (batch real).
2. Registra todas as entradas em `_subscriptions`.
3. Retorna o número de entradas enviadas.

### `registrar_status(codigo: str) -> int`
**Garante:**
1. Delega para `registrar_topico(codigo, FieldName.STATUS)`.

### `_enviar_raw(comando: str)`
**Garante:**
1. Envia `comando + "\n"` via `socket.sendall`.
2. Em caso de erro, marca `_conectado = False`.
3. Sempre dorme `max(_send_delay_s, 0.001)` após envio.

### `ler_campo_cache(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Busca no cache interno `_cache` pela chave `(codigo.upper(), campo_str)`.
2. Thread-safe via `_mutex`.
3. Converte string para float (substituindo `,` por `.`).
4. Retorna `None` se valor é `0` (diferente do RTDProfit que retorna `0.0`). POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: comportamento diferente entre adapters pode causar inconsistência.

### `ler_campos(codigo: str, *campos: FieldName) -> dict[FieldName, float | None]`
**Garante:**
1. Lê múltiplos campos de uma vez, com um único lock.
2. Retorna dict `{FieldName: valor}`.

### `ler_status_cache(codigo: str) -> str`
**Garante:**
1. Busca campo `"ST"` no cache (não `"EST"` como no Profit).
2. Normaliza via `_STATUS_NORMALIZE`: `"A"` → `"Aberto"`, `"L"` → `"Leilão"`, `"F"` → `"Fechado"`.

### `forcar_leitura(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Invalida o cache do campo, re-registra o tópico e faz polling (até 50 tentativas com 10ms de intervalo) esperando um valor > 0.
2. Se não conseguir, retorna o valor antigo (antes da invalidação).

### `refresh(timeout_ms: int = 0) -> dict[str, object]`
**Garante:**
1. Retorna dict de chaves sujas (`_dirty_keys`) desde o último refresh.
2. Limpa `_dirty_keys` após a leitura.
3. Ignora `timeout_ms` — o modo push não precisa de timeout.

### `reconectar(max_attempts=5, delay_s=3.0) -> bool`
**Garante:**
1. Desconecta primeiro, depois tenta `_conectar()` até `max_attempts` vezes com backoff linear (`delay_s * tentativa`).
2. Se conectar, chama `_re_registrar_pendentes()` para reenviar todas as subscriptions.
3. Retorna `True` se reconectou.

### `_re_registrar_pendentes()`
**Garante:**
1. Reenvia todas as subscriptions armazenadas em `_subscriptions` após reconexão.

### `invalidar_cache(codigo: str, campo: FieldName)`
**Garante:**
1. Remove a entrada do `_cache` (não remove a subscription — o tópico continua registrado).

### `get_idade_campo(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Retorna `time.time() - cache_ts` (idade em segundos desde a última atualização).
2. `None` se o campo nunca foi recebido.

### `get_ts_campo(codigo: str, campo: FieldName) -> float | None`
**Garante:**
1. Retorna o timestamp absoluto da última atualização do campo.

### `desconectar()`
**Garante:**
1. Marca `_conectado = False`.
2. Aguarda 50ms para a thread leitora encerrar.
3. Limpa `_cache` e `_cache_ts` sob lock.
4. Faz `shutdown(SHUT_RDWR)` + `close()` no socket.

### `_thread_leitora()` (privada)
**Garante:**
1. Loop bloqueante em `recv(65536)`.
2. Acumula dados em buffer, processa linha a linha (delimitador `\n`).
3. Linhas `SYN` atualizam `_ultimo_syn` (heartbeat).
4. Linhas `SQT` são parseadas via `_parse_linha` e acumuladas em `atualizacoes`.
5. A cada batch de atualizações, adquire `_mutex` e atualiza `_cache`, `_cache_ts`, `_dirty_keys` em bloco.
6. Profiling: loga estatísticas a cada 30 segundos.

### `_parse_linha(linha: str) -> tuple | None`
**Garante:**
1. Separa por `\x01` (SOH) como delimitador primário, `#` como fallback.
2. Espera formato `SQT<SEP>CODIGO<SEP>CAMPO<SEP>VALOR`.
3. Converte valor para `float` se possível, senão mantém como `str`.
4. Retorna `((codigo.upper(), campo), valor)` ou `None`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `socket` | `socket` | Conexão TCP |
| `threading` | `threading` | Thread leitora + mutex |
| `time` | `time` | Timestamps, sleeps, profiling |
| `logging` | `logging` | Logger |
| `src.domain.services.market_data_source` | `FieldName`, `OPENFAST_FIELD_STR` | Tradução FieldName → str |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 386 |
| Última modificação | 2026-08-06 |
| Classes | 1 (`OpenFastSocketAdapter`) |

## Notas

- 2026-08-10 — STALE Fase 1: `allow_stale`, `stale_campo_s`, `is_stale_campo`, watchdog.
- **`allow_stale`:** `ler_campo_cache(codigo, campo, allow_stale=False)` — se `True`, ignora janela de idade e retorna valor cacheado mesmo se velho. `ler_campos` e `forcar_leitura` também aceitam o parâmetro.
- **`stale_campo_s`:** Parâmetro no `__init__` (default 15.0). Property exposta. Usado por `ler_campo_cache`, `ler_campos` e `is_stale_campo` para determinar se um campo excedeu a idade máxima.
- **`is_stale_campo(codigo, campo) -> bool`:** Retorna `True` se o campo existe no cache mas sua idade excede `stale_campo_s`.
- **Normalização negativa:** `ler_campo_cache` mapeia `v < 0 → None` (alinhado com `rtd_profit`). Zero retorna `0.0`.
- **Watchdog:** `verificar_conexao` detecta thread leitora morta com `_conectado` ainda `True` e invalida o cache inteiro ao detectar desconexão.
- **Origem timestamps:** `get_ts_origem(codigo)` retorna timestamp de origem (TIME/TIMENEG do protocolo OpenFast). `get_idade_origem(codigo)` retorna idade real da cotação.
- `ler_campo_cache` retorna `None` para valor `0`, enquanto `RTDProfitAdapter` retorna `0.0`. Inconsistência conhecida — chamadores tratam ambos como "sem dado".
- O campo de status é `"ST"` (não `"EST"` como no Profit). A normalização converte para "Aberto", "Leilão", "Fechado".
- O separador `\x01` (SOH) é o delimitador padrão do protocolo. Fallback `#` para compatibilidade.
- `forcar_leitura` faz polling ativo por até 500ms (50 × 10ms), bloqueante diferente do adapter RTD.
