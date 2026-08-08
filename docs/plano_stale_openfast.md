# Plano evidenciado: dados antigos via OpenFast no SpreadHunter

**Status:** proposta para revisão (submetida também a Opus / DeepSeek)
**Escopo:** impedir que o SpreadHunter gere sinal/sem sinal velho vindos do feed OpenFast (socket TCP 557)
**Datado:** sessão de diagnóstico baseada no manual oficial `OpenFastV2.pdf` (23 páginas) + inspeção do código.

---

## 1. Sobre o problema

Ao usar `fonte_market_data = "openfast"`, o SpreadHunter apresenta **dado antigo como se fosse vigoroso**: sinais/oportunidades montados com cotação que não foi atualizada após a requisição atual.

Isso **não** é um problema de "histórico enviado pelo servidor" — o manual mostra que o SQT é serviço **streaming, só assinatura, sem replays históricos**. O que o sistema envango faz é **preservar e reutilizar o último valor recebido** como se fosse atual, mesmo quando a conexão/cache não comprova mais frescor.

### Cultura manual (evidência)

| Fonte | Trecho |
|---|---|
| FCA pág. 2 §4 | Field separator é `\001` (SOH). Representado `#` no manual. |
| FCA pág. 2 §5 | Heartbeat `SYN` a cada 15s — confirma **conectividade**, não cotação. |
| FCA pág. 3 §6 (SQT) | "serviço **streaming, de assinatura**. Uma vez que enviou a requisição, o FAST enviará **todas as mudanças** sem precisar ficar requisitando". Campos LISTA/TIME/ASK/BID/TIMENEG etc. |
| FCA pág. 5 §7 (TICKS) | "irá **sempre retornar os últimos 100 ticks** e depois terminar com 'E'". |

Conclusão do manual: para o serviço TICKS o snapshot/streaming é repetível (100 + E). Para SQT não existe "histórico" — todo valor chega por push.

---

## 2. Causa raiz (identificada no código)

O SpreadHunter usa o cache do adaptador como **fonte da verdade**, sem validar que o valor foi entregue/atualizado após o último ciclo. Três pontos de falha:

### 2.1 Idade = entrega ao Python, não idade da cotação

- `src/infrastructure/providers/openfast_socket_adapter.py:310` registra apenas `_cache_ts[chave] = agora` (relógio local do processo).
- Não existe assinatura de `TIMENEG`/`TIME`, embora o manual §6 disponibilize para SQT.
- IGUAL: um ASK que não muda há 40min fica "de idade 5s" no cache (porque a thread leitora o regravou ou o SYN o manteve vivo), e continua alimentando sinal.

### 2.2 Fallback silencioso do cache antigo

- `openfast_socket_adapter.py:219-228` `forcar_leitura()`:
  ```
  old = self.ler_campo_cache(codigo, campo)
  self.invalidar_cache(codigo, campo)
  self.registrar_topico(codigo, campo)
  for _ in range(50): ...
  return old        # ← se nada chegou em 500ms, DEVOLVE o velho
  ```
  Chamado por `export_dialog.py:354` e `monitor_worker.py` (via `forcar_leitura`), usado para preço ao vivo.
- `mercado_data_provider.py`:
  - `escape` `self._dados_cache[key]` A139: reusa o `entry` inteiro quando `cab_mudou = False` / não houve dirty (linhas 533–543) → o book chega de um ciclo a outro **sem nenhuma nova atualização** nos campos de preço.
  - Fallbacks `p_ativo = self._precos_ativo_cache.get(...)` em 554, 602 e 648 → devolve preço de um período bem anterior.
  - Linha 535 `entry = self._dados_cache[key]` + só re-lê status; os campos de book não são revalidados.

### 2.3 `dados_stale` existe mas não bloqueia cadastro de oportunidade

- A flag `dados_stale` hoje é **só informativa/exibida no Dashboard de Performance** (`monitor_worker.py:1179»`, `get_engine_stats` linha 819). Não é propagada para **rejeitar** cálculo de oportunidade quando uma das pernas está velha.

---

## 3. Proposta de solução — estado STALE sem perder diagnóstico

Princípio:
> **heartbeat vivo ≠ cotação fresca.** O valor deve ser usado em **cálculo/sinais apenas se o campo tiver sido atualizado dentro da janela `stale_campo_s`**. Fora disso, o campo está STALE: **mantido apenas para diagnóstico/UI**, jamais para calcular box/collar/mpp/alerta.

### 3.1 API (interface `MarketDataSource`)

Adicionar comportamento estável ao protocol:

- `ler_campo_cache(codigo, campo, allow_stale=False)` → retorna `None` quando o valor está fora da janela de frescor; retorna o valor com `allow_stale=True` apenas para diagnóstico.
- `ler_campos(..., allow_stale=False)` id$em.
- novos helpers: `is_stale_campo(codigo, campo) -> bool` e `get_idade_campo(codigo, campo)` já.
- **Default `allow_stale=False`** — em TODOS os caminhos de cálculo/sinal da propriedade receptora.
  - `allow_stale=True` somente em: exportar/UI/diagnóstico, logs, "OLHAR".

### 3.2 Adaptador OpenFast (socket)

1. Mantém coleta: `_cache[codigo,campo] = valor; _cache_ts[chave] = agora`.
2. `_parse_linha` — além de alter ações, marca `chave[0]` como "touched".
3. Guard da janela: `now - _cache_ts[chave] > _stale_campo_s ⇒ STALE` (campo responsável a Null, mantida cópia didagnóstica `_cache_stale_rel` com `received_ts`, `stale_age`).
4. **OBS (muda o custo de age anterior):** idade relativa da sessão:
   - Valores > `stale_campo_s` da janela de corte são `STALE`.
   - Abaixo de `stale_campo_s` (ex.: 15 s): `_cache_ts` mede **entrega**; se quis **idade de cotação real**, assinar `TIMENEG`/`TIME` p/ subjacente (parâmetro `assinar_timestamp_openfast`, default **0** = off).
5. **Watchdog conexão** (resolve 2.1/falha de thread):
   - NO `_thread_leitora`: trata-known `FileNotFoundErrorEWCH`, socket exceptions, `dados vazio`.
   - (adicional) uma task de calculadora checa `thread.is_alive()` + `_ultimo_syn` + `_dados` recebidos; se thread morreu e `_conectado` ainda True → marcar `feed_state = "DISCONNECTED"`, `_conectado=False`, invalidar cache.
6. **subscription_generation** (sessão de assinatura):
   - Incrementar a cada nova conexão/reconexão e a cada (re)assinatura. Limpar `_cache`/`_cache_ts` ao desconectar/reconectar (já existe em `desconectar` linha 370-386) e **forçar que `data antiga de sessão anterior` nunca reassome à nova** — sem isso, a nova sessão nasce com timestamp da cação antiga.
7. `forcar_leitura()` — **nunca** retornar valor com... no default `allow_stale=False`: após `stale_campo_s` sem atualização, retornar `None`; manter valor antigo apenas quando `allow_stale=True`. **Remover o fallback silencioso `return old`.**

### 3.3 Contrato de frescor (garantias de design)

1. **SYN nunca atualiza `_cache_ts` de ASK/BID** — o heartbeat apenas mantém `_ultimo_syn` (conectividade). Nunca serve para "atualizar" timestamp de campo de cotação. (Já é verdade hoje: `openfast_socket_adapter.py:297-299` apenas seta `_ultimo_syn` e `continue`.)
2. TIME/TIMENEG **apenas diagnóstico complementar** — nunca usado como timestamp automaticamente associado ao ASK/BID recebido. Se ativado (`assinar_timestamp_openfast`), alimenta coluna de diagnóstico do payload, jamais reescreve `_cache_ts`.
3. `forcar_leitura` aguarda **evento novo pós-chamada**: grava o contador `_update_counter`/geração antes de chamar e só aceita um valor cuja chegada tenha gerado atualização posterior; caso contrário retorna `None`. Nunca aceita valor pré-existente sem evidência de entrega nova.

### 5.1 Provider + cálculo (bloqueio de sinal em qualquer perna stale)

- `market_data_provider.capturar_dados_mercado()`:
  - Ao ler campos p/ `entry` (Onda 1/2/cab-skip) usar `allow_stale=False` sempre.
  - Anotar em `entry`: `ts_ativo_ask`, `ts_ativo_bid`, `stale_*`, `feed_state`, `subscription_generation`.
  - **NÃO persistir/reaproveitar `_dados_cache[key]` se os campos de book estavam stale** — em vez disso, marcar o entry como STALE (`entry["stale"]=True`) e re-forçar registra-se, mas **não alimentar calculadoras com esse entry**.
- **Gate nos use cases/calculadoras:** qualquer campo crítico (isor `ASK`/`BID` de perna, `preco_ativo`) com `is_stale_campo()` = descarta a oportunidade para aquele par ("não é uma oportunidade agora"). Não altera **parâmetros do box/collar** nem **regras de estratégia** — apenas o gate de entrada de dados.

### 6. Parâmetros (BD-first — regras do projeto)

| Chave | Default | Descrição |
|---|---|---|
| `stale_campo_s` | `15` | Janela de frescor do campo (não receb.Eco). Campo além disso = STALE (None p/ sinal). |
| `stale_sinal_s` | `30` | **Tolerância entre pernas** (separada de `stale_campo_s`): nº de pernas stale/mix de idades que bloqueia cálculo. Não é a mesma coisa da janela do campo. |
| `assinar_timestamp_openfast` | `0` | 1 = subscrever TIME/TIMENEG apenas p/ diagnóstico (nunca vira ts do ASK). |

Arquivos a tocar: `config/parametros_default.json`, `parametro_operacional.py` (fallback), `parametros_widget.py`, `regras_dialog.py` (exposição).

---

## 7. Cronograma de implementação (incremental)

**Fase 1 — correção mínima (foco no bug de produção):**
1. OpenFast adapter: `_stale_campo_s`, `allow_stale`, **`forcar_leitura` sem `old`** (evento novo pós-chamada), `subscription_generation`, watchdog de thread, invalidação na desconexão/reconexão.
2. Provider: gate `allow_stale=False`, anotações `ts/stale/feed_state`, **não reaproveita entry stale** (`_dados_cache`/`_precos_ativo_cache`).
3. Rodar/atualizar os testes de OpenFast/provider **antes** de tocar outros adaptadores.

**Fase 2 — generalização:**
4. Interface `MarketDataSource.ler_campo_cache(..., allow_stale=False)` + `is_stale_campo()` — replicar para Profit/RTD, FastTrade e mock (sem mudar o contrato interno dos mesmos).
5. Use cases/calculadoras: descarta oportunidade se qualquer perna `stale` (regras de estratégia intactas).
6. Parâmetros (item 6) + `get_engine_stats` passa a emitir `stale_count`/`feed_state`.
7. Logs `STALE`, `DISCONNECTED`, `NO_NEW_UPDATE` (com `received_ts`, `cache_ts`, `stale_age`, `subscription_generation`, motivo).

---

## 8. Testes a criar/atualizar

| # | Caso |
|---|---|
| T1 | `forcar_leitura()` timeout → retorna `None` (nunca valor antigo) com `allow_stale=False`. |
| T2 | cache com idade > `stale_campo_s` → `None` no sinal; valor visível com `allow_stale=True`. |
| T3 | thread leitora morta → detecção, `feed_state=DISCONNECTED`, cache invalidado. |
| T4 | reconnection → `subscription_generation+1`, cache limpo, sem ressurreição da sessão antiga. |
| T5 | `allow_stale` default `False` em todos os caminhos de cálculo. |
| T6 | uma perna stale → use case não gera a oportunidade; log `NO_NEW_UPDATE`. |
| T7 | basics: SQT parsing, SYN, revertões (regressão OpenFast) ainda passam. |

Executar: `python -m pytest tests/ -x -q --tb=short` (585 testes atuais) e os testes específicos de OpenTail/provider.

> **Regras de negócio invariáveis (mantém `as-is`):** strike nunca persistido (vem do RTD); `MOD` só de CALL; custos B3 por prêmio (×2); chave composta `ativo|cod_opcao`; coerência book BID/ASK (of_compra = BID, of_venda = ASK); box 4P `lucro = clr - distância` (short), sem inverter.

---

## 9. O que este plano NÃO fará

- Não trocar a fonte de dados como solução única.
- Não descartar tick/TICKS.
- Não mudar parâmetros de estratégia (box/collar/mpp) nem regras de book.
- Não usar o `SYN` como prova de atualização do ASK/BID — apenas da saúde da conexão.
- Tempo/TIMENEG entram só como diagnóstico, nunca para "fabricar" frescor de ASK/BID.
- Fase 1 não altera os demais adaptadores; testes de OpenFast/provider rodam antes de generalizar.