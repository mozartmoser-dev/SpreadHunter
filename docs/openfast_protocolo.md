# Protocolo OpenFast — Referência de Consulta

Fonte: manual oficial da FAST TRADE (API Open Fast). Cruzado com o código real
(`src/infrastructure/providers/openfast_socket_adapter.py` e
`src/domain/services/market_data_source.py`).

**Onde entra no app:** `fonte_market_data = "openfast"` (socket TCP local). Adapter:
`OpenFastSocketAdapter`.

---

## 1. Conexão

- **Endereço:** `127.0.0.1`, **porta 557** (socket TCP).
- **Handshake:** ao abrir o socket, enviar o comando `OPENFAST`.
  Retorno: linha com a versão, ex.: `version#1.0`.
- **Pré-requisito:** o FAST TRADE deve estar executando e conectado.
- **Limite:** nesta versão, **só 1 conexão por vez**. Se outra conexão estiver ativa, o
  servidor responde: `Não é possível criar mais de uma conexão com o OpenFast!`
  → o adapter loga `servidor ocupado (outro cliente conectado)` e mantém `_conectado = False`.
- **Comandos:** sempre em **LETRAS MAIÚSCULAS**.

### No adapter (`_conectar`, linha 201)
```python
sock.sendall(b"OPENFAST\n")
# aguarda linha que começa com "version" em até 5s
```

---

## 2. Separador de campos

`\001` (SOH, ASCII 1). **Importante:** neste arquivo (e no manual) o separador é
representado como `#` para facilitar a leitura.

### No adapter (`_SEP`, linha 14)
```python
_SEP = "\001"
```

---

## 3. Heartbeat (SYN)

- O servidor envia `SYN` **a cada 15 segundos** — confirma **conectividade** do sistema,
  **NÃO** atualização de cotação.
- Ausência de `SYN` > 20s ⇒ `disponivel == False` no adapter (`_ultimo_syn`).
- **Regra de negócio:** `SYN` nunca renova a idade de ASK/BID (ver `docs/plano_stale_openfast.md`).

### No adapter (`_thread_leitora`, linha 479)
```python
if linha.startswith("SYN"):
    self._ultimo_syn = time.time()
    continue
```

---

## 4. SQT — Cotação (Market Data) ★ USO PRINCIPAL DO APP

Serviço **streaming de assinatura**. Assinou uma vez → o servidor envia todas as mudanças
sem nova requisição. **Só é possível solicitar UM campo por comando.**

### Requisição
```
on#SQT#ATIVO#CAMPO
```

### Campos aceitos (campo real no socket)

| Campo | Significado |
|---|---|
| `LAST` | Preço do último negócio |
| `VAR` | Variação em percentual |
| `ASK` | Melhor oferta de Venda (você paga) |
| `VOLASK` | Volume da melhor oferta de Venda |
| `BID` | Melhor oferta de Compra (você recebe) |
| `VOLBID` | Volume da melhor oferta de Compra |
| `TIME` | Horário da mensagem (`hh:mm:ss`; também fração de dia) |
| `TIMENEG` | Horário do último negócio |
| `QTLAST` | Quantidade do último negócio |
| `HIGH` | Máxima do dia |
| `LOW` | Mínima do dia |
| `OPEN` | Abertura do dia |
| `CLOSE` | Fechamento do último pregão |
| `VOLQ` | Volume de papéis negociados no dia |
| `VOLF` | Volume financeiro negociado no dia |
| `QTT` | Quantidade de negócios |
| `DATE` | Data da cotação (`yyyyMMdd`) |
| `ST` | Status do ativo |
| `DIF` | Variação em preço/pontos |
| `AJU` | Valor do Ajuste |
| `AJULAST` | Ajuste do dia anterior |
| `TEOPR` | Preço Teórico |
| `TEOVOL` | Volume Teórico |
| `CAB` | Contratos em Aberto |

> **Erratas do manual:** o manual escreve `VOALSK` (typo — o correto é `VOLASK`); a
> descrição de `VOLBID` diz "Venda" mas é o volume da melhor oferta de **Compra**.

### Retorno
```
SQT#ativo#CAMPO#VALOR
```

### Mapeamento para o app (`OPENFAST_FIELD_STR`, market_data_source.py:43)

| FieldName (app) | String no socket |
|---|---|
| `STRIKE` | `PEX` (NÃO documentado no manual; nunca deduzir strike pelo código B3) |
| `LAST_PRICE` | `LAST` |
| `BID` | `BID` |
| `ASK` | `ASK` |
| `STATUS` | `ST` |
| `QTD_LAST` | `QTLAST` |
| `VOL_BID` | `VOLBID` |
| `VOL_ASK` | `VOLASK` |
| `CLOSE` | `CLOSE` |
| `OPEN` | `OPEN` |
| `VARIATION` | `VAR` |
| `TIME` | `TIME` |
| `TIMENEG` | `TIMENEG` |

> `HIGH`, `LOW`, `VOLQ`, `VOLF` não estão em `OPENFAST_FIELD_STR` (existem no
> `FASTTRADE_FIELD_STR`).

### No adapter (`registrar_topico`, linha 273)
```python
self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo.upper()}{_SEP}{campo_str}")
```

---

## 5. TICKS — Negócios Realizados (Trades)

Snapshot dos **últimos 100 ticks**, depois terminador `E` e então streaming.

```
on#TICKS#ATIVO
TICKS#petr4#12:07:28.415#38.76#16#39#100#145840#0#C
...
TICKS#petr4#E        <- fim do snapshot (daqui em diante é streaming)
```

Campos do retorno: TICKS · ATIVO · Horário · Preço · Corretora Compra · Corretora Venda ·
Quantidade · TradeID · Tipo (0=NORMAL, 1=DIRETO, 2=RLP) · Agressor (C=Comprador, V=Vendedor).

---

## 6. BRKSLD — Saldo das Corretoras

```
on#BRKSLD#ATIVO#PERÍODO     # ativar
off#BRKSLD#ATIVO#PERÍODO    # remover assinatura
```

`PERÍODO`: 0 (dia), 1, 2, 5, 10, 15, 30 ou 60.

Retorno: `BRKSLD#ATIVO#PERÍODO#...` (série de campos por corretora: código, nome, saldo
volume, preço médio, agressões, passivo, RLP, direto, L/P, volumes/qtds).

---

## 7. SAB — Livro de Ofertas por Preço (Book Agregado)

15 melhores ofertas de compra + 15 de venda.

```
on#SAB#ATIVO    # ativar
off#SAB#ATIVO   # remover assinatura
```

Retorno: `SAB#ATIVO#POSIÇÃO#LADO#QTD_OFERTAS#VOLUME#PREÇO`
( Lado: `C`=compra, `V`=venda).

---

## 8. Envio de Ordens

Trava de segurança: **2 ordens por segundo**. Requer FAST TRADE conectado à Corretora.

| Serviço | Tipo |
|---|---|
| `on#ORDERSEND#...` | Limite |
| `on#ORDERSENDMKT#...` | A Mercado (com resto a limite) |
| `on#ORDERSENDSTOP#...` | STOP |
| `on#ORDERSENDOCO#...` | OCO (one-cancel-other) |
| `on#ORDERSENDOSO#...` | OSO (one-send-other) |

Campos comuns (obrigatórios marcados com *): `*Identificador` (único no dia) ·
`*Ativo` · `*Quantidade` · `*Preço` (conforme serviço) · `*Conta` ·
`*Lado` (1=compra, 2=venda) · `*Duração` (0=Dia, 1=VAC, 3=Executa/Cancela, 6=Até a Data) ·
Data Validade (se Duração=6) · Qtd Aparente · Qtd Mínima · Rótulo · Operação (DT | POSITION).

Ex.: `on#ORDERSEND#OpenFast171525#WINM23#5#160000#9900249160#1#0####ROTULO##`

---

## 9. Edição / Cancelamento de Ordem

```
on#ORDEREDIT#ID#QTD#PRICE#STOPX
on#ORDERCANCEL#ID
```

- OSO: só edita preço de entrada. LIMITE: só `PRICE`. OCO: não altera quantidade.

---

## 10. SIGNORDERS — Recebimento de ordens em tempo real

Assinar logo na inicialização do algoritmo:

```
on#SIGNORDERS
```

Retorno: `SIGNORDERS#ORDERID#DATAHORA#CLORDID#ORDSTATUS#LOGIN#ACCOUNT#SYMBOL#SIDE#ORDERQTY
#LASTQTY#CUMQTY#LEAVESQTY#PRICE#LASTPX#AVGPX#MARKET#ORDERTAG#TEXT#TIPO#STOPPX#VALIDADE#CLORDLINK`

`ORDSTATUS`: R=RECEIVED · A=PENDING_NEW · 0=NEW · 1=PARTIALLY_FILLED · 2=FILLED ·
6=PENDING_CANCEL · 4=CANCELED · 5=REPLACED · E=PENDING_REPLACE · 8=REJECTED ·
C=EXPIRED · H=TRADE_CANCEL.

`SIDE`: 1=Compra, 2=Venda. `TIPO`: 1=Mercado, 2=Limite, 4=STOP.

---

## 11. ORDERQUERY — Status de uma ordem

```
on#ORDERQUERY#ID
```
Retorno: `ORDERQUERY#...` (mesma estrutura do SIGNORDERS).

---

## 12. ORDERMASS — Lista de ordens do dia

```
on#ORDERMASS#TIPO      # TIPO = ALL | OPEN
```
Request/response. Retorno: `ORDERMASS#TIPO#...` (mesma estrutura de ordem).

---

## 13. POS — Posição da Conta em um ativo (streaming)

```
on#POS#CONTA#ATIVO
```
Retorno: `POS#CONTA#ATIVO#PM_Compra#PM_Venda#Qtd_aberta#PM_aberta#LP_Aberto#LP_Fechado
#LP_Total#Qtd_Vendida#Qtd_Comprada`.

---

## 14. POSFLATTEN — Zeragem de posição do dia

```
on#POSFLATTEN#CONTA#ATIVO
```
Zera posição aberta no dia (não considera custódia de outros dias). Ordens em aberto são canceladas.

---

## 15. Desconexão ⚠️

**O manual NÃO documenta comando de logout/encerramento da conexão.** Os únicos comandos
`off` documentados são para **remover assinaturas** (`off#BRKSLD`, `off#SAB`); não há
`off` para a conexão principal nem para assinaturas SQT.

Consequência prática (sintoma relatado): ao fechar o app e reabrir, o servidor pode
responder `Não é possível criar mais de uma conexão com o OpenFast!` — o servidor mantém o
slot da conexão anterior. O adapter `desconectar()` (openfast_socket_adapter.py:669) faz
`shutdown(SHUT_RDWR)` + `close()` do socket, mas **não envia nenhum comando** ao servidor.

### No adapter (`desconectar`, linha 669)
```python
self._conectado = False
self._socket.shutdown(socket.SHUT_RDWR)   # + close()
self._reader_thread.join(timeout=0.5)
self._cache.clear()  # + _cache_ts, _cache_ver, _dirty_keys
```

> **Status da investigação:** é o problema reportado pelo usuário (fechar/reabrir o app
> exige reiniciar o FAST TRADE). Ver histórico em `SKILL.md`. Alternativa a avaliar:
> enviar `off#SAB`/desassinaturas antes do close, ou aguardar o timeout do servidor.

---

## 16. Exemplo em Python (oficial)

https://files.cedrotech.com/Cedro/OpenFast/PyExemplo.zip

---

## 17. Resumo dos comandos

| Comando | Serviço | Streaming? |
|---|---|---|
| `OPENFAST` | Handshake (retorna versão) | — |
| `on#SQT#ATIVO#CAMPO` | Cotação (1 campo/comando) | sim |
| `on#TICKS#ATIVO` | Trades | sim (snapshot 100 + E) |
| `on/off#BRKSLD#ATIVO#PERÍODO` | Saldo corretoras | sim |
| `on/off#SAB#ATIVO` | Book agregado | sim |
| `on#ORDERSEND*#...` | Envio de ordens | — |
| `on#ORDEREDIT#...` | Edição de ordem | — |
| `on#ORDERCANCEL#ID` | Cancelamento | — |
| `on#SIGNORDERS` | Recebimento de ordens | sim |
| `on#ORDERQUERY#ID` | Status de ordem | — |
| `on#ORDERMASS#TIPO` | Lista de ordens do dia | — |
| `on#POS#CONTA#ATIVO` | Posição | sim |
| `on#POSFLATTEN#CONTA#ATIVO` | Zeragem de posição | — |