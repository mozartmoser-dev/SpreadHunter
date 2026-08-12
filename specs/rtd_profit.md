# RTDProfit

Cliente COM (Component Object Model) para o servidor RTD (Real-Time Data) do Profit Pro. Conecta-se ao servidor `rtdtrading.rtdserver`, gerencia tópicos de assinatura com contador aleatório para evitar colisões com execuções anteriores, e fornece cache local de valores com refresh via `RefreshData`.

## Contrato (Requisitos)

### `__init__()`
**Garante:**
1. Inicializa `_topic_counter` com um valor aleatório entre 100.000 e 20.000.000 para evitar colisão de IDs de tópico com execuções anteriores que possam ter ficado ativas no servidor RTD do Profit.
2. Tenta `_conectar()` — se `pywin32` não estiver instalado, `disponivel = False`.
3. Tenta `ServerStart` com callback (`_RTDCallback`) e sem callback como fallback.

### `_conectar()`
**Garante:**
1. Cria `Dispatch(RTD_SERVIDOR)` via `win32com.client`.
2. Cria `_RTDCallback` com método `UpdateNotify` vazio (callback não faz nada — refresh é polling).
3. Tenta `ServerStart` com callback e sem callback (`None`). Se ambos falharem, tenta `ConnectData` mesmo assim.
4. Se `pywin32` não estiver instalado (`ImportError`), loga warning e mantém `disponivel = False`.
5. Se qualquer outro erro ocorrer, loga warning e mantém `disponivel = False`.

### `_topic_id(codigo: str, campo: str) -> int`
**Garante:**
1. Chave composta `"codigo|campo"`.
2. Thread-safe via `self._lock`.
3. Se a chave não existe, incrementa `_topic_counter` e cria mapeamento bidirecional (`_topic_map` + `_topic_reverse`).

### `registrar_topico(codigo: str, campo: str) -> int`
**Garante:**
1. Obtém ou cria o topic ID.
2. Se já tem valor no cache (`_valores`), retorna o tid sem chamar `ConnectData`.
3. Chama `self._rtd.ConnectData(tid, [topico, campo], True)` — o terceiro argumento `True` significa "get new value" (força refresh).
4. Em caso de exceção, armazena `None` no cache.
5. Retorna o topic ID.

### `invalidar_cache(codigo: str, campo: str)`
**Garante:**
1. Chama `DisconnectData(tid)` no servidor RTD.
2. Remove o tid de `_valores`, `_topic_map` e `_topic_reverse`.
3. Thread-safe via lock.

### `registrar_status(codigo: str) -> int`
**Garante:**
1. Equivalente a `registrar_topico(codigo, "EST")`, mas o tópico RTD é apenas `codigo` (sem sufixo `_B_0`).
2. Usa `ConnectData(tid, [codigo, "EST"], True)`.

### `_parse_refresh_result(resultado) -> dict[str, object]`
**Garante:**
1. Se `resultado` é `None` ou `int`, retorna `{}`.
2. Extrai `data` e `update_count` de `resultado[0]` e `resultado[1]`.
3. Se `update_count == 0`, retorna `{}`.
4. Itera sobre `topics` e `values` retornados pelo RTD, atualizando `_valores` e construindo dict `{chave: valor}` para chaves que mudaram.
5. Converte `raw_tid` para `int` (pode vir como tuple `(tid,)`).

### `refresh(timeout_ms: int = 0) -> dict[str, object]`
**Garante:**
1. Se `timeout_ms > 0`, respeita o intervalo mínimo entre refreshes (debounce). POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: `timeout_ms` é usado como debounce interval, não como timeout real. O valor `0` passado para `RefreshData` faz o servidor RTD retornar imediatamente sem esperar mudanças.
2. Chama `self._rtd.RefreshData(0)` e delega parse para `_parse_refresh_result`.
3. Retorna `dict[str, object]` com chaves no formato `"codigo|campo"`.

### `ler_campo_cache(codigo: str, campo: str) -> Optional[float]`
**Garante:**
1. Busca no cache local (`_valores`) pelo tid mapeado.
2. Converte `str` para `float`, substituindo `,` por `.`.
3. Retorna `0.0` se o valor for `<= 0` (POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: valor zero legítimo é indistinguível de ausência).
4. Retorna `None` se não encontrado ou não parseável.

### `ler_status_cache(codigo: str) -> str`
**Garante:**
1. Busca `"codigo|EST"` no cache local.
2. Retorna string vazia se não encontrado.

### `ler_campo(codigo: str, campo: str) -> Optional[float]`
**Garante:**
1. Leitura one-shot síncrona via `ConnectData(tid, [topico, campo], False)` — o `False` significa usar cache do servidor.
2. Converte para `float`, retorna `0.0` se `<= 0`.

### `forcar_leitura(codigo: str, campo: str) -> Optional[float]`
**Garante:**
1. Leitura one-shot com `ConnectData(tid, [topico, campo], False)`, mas atualiza o cache local com o valor obtido.
2. Força o servidor RTD a buscar o valor na fonte, sem usar cache interno do servidor.

### `reconectar() -> bool`
**Garante:**
1. Se `_rtd` não é `None`, tenta `ServerStart(None)`.
2. Se `_rtd` é `None`, chama `_conectar()` novamente.
3. Retorna `True` se conectado, `False` caso contrário.

### `desconectar()`
**Garante:**
1. Limpa todos os caches (`_topic_map`, `_topic_reverse`, `_valores`).
2. Chama `DisconnectData(tid)` para cada tópico registrado.
3. Não quebra se `_rtd` já estiver `None`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger do módulo |
| `threading` | `threading` | `Lock` para thread-safety nos caches |
| `time` | `time` | Debounce no `refresh()` |
| `typing` | `Optional` | Type hints |
| `src.infrastructure.providers.rtd_config` | `RTD_SERVIDOR`, `rtd_topico` | Constante do ProgID COM e formatação de tópico |
| `win32com.client` (runtime) | - | `Dispatch` para criar objeto COM |
| `win32com.server.util` (runtime) | - | `wrap` para callback COM |
| `random` (runtime) | - | Inicialização do `_topic_counter` |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 272 |
| Última modificação | 2026-07-09 |
| Classes | 2 (`RTDProfit`, `_RTDCallback` interna) |

## Notas

- 2026-07-09 — última modificação registrada no git.
- O `timeout_ms` no `refresh()` não é um timeout real — é um debounce interval. O valor `0` passado para `RefreshData` faz o COM retornar imediatamente sem esperar dados novos. O mecanismo real de throttle é o debounce baseado em `_ultimo_refresh_timestamp`.
- `ler_campo_cache` e `ler_campos` normalizam valores negativos para `None` (commit `e89242c`). Valor `0.0` é retornado como `0.0` (distinguível de ausência). Antes retornava `0.0` para `<= 0`, mascarando zeros legítimos.
- `__init__` aceita `progid` opcional para alternar ProgID COM (ex: Fast Trade).
- `_topic_counter` é inicializado com `random.randint(100000, 20000000)` para evitar colisão com execuções anteriores. Isso é necessário porque o servidor RTD do Profit pode manter tópicos de uma execução anterior ativos, e reutilizar os mesmos IDs causaria conflito.
- Importações condicionais (`win32com`, `random`) são feitas dentro dos métodos, não no topo do arquivo, para permitir que o módulo seja importado mesmo sem pywin32.
