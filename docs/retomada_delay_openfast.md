# Retomada: diagnóstico e conserto do delay OpenFast (T1–T6)

**Status:** fix aplicado e verde (663 testes). Validação final pendente no mercado aberto.
**Datado:** 10/08/2026 (sessão noturna; mercado fechou 17:00). Retomar ao rodar em pregão.
**Leia também:** `docs/plano_stale_openfast.md` (plano anterior de STALE, contexto de causa raiz).

---

## 1. Objetivo da sessão

Encontrar o gargalo/delay do caminho OpenFast (socket TCP 557, FastTrade) e removê-lo,
**preservando as funcionalidades existentes** (BOX4P, PUT_RATIO, MPP, COLLAR_CAL e demais
scanners não podem deixar de produzir resultados).

Restrições do usuário:
- Testar **sem a interface** (app pode estar fechado); FastTrade deve estar aberto.
- Concentrar-se **apenas no OpenFast socket** (não mexer RTD/Profit a menos que necessário).
- **Não adicionar logs/medidores novos permanentes** — instrumentação de diagnóstico é temporária.
- **Sempre propor → confirmar → aplicar** (regra AGENTS.md). Usuário confirmou explicitamente o fix dos consumidores com "se vc souber o que está fazendo aplique".

---

## 2. Onde vive cada ponto de tempo (T1–T6)

Instrumentação existente em `src/infrastructure/providers/stale_trace.py` (pré-Fase 2, temporária;
docstring manda remover após o diagnóstico; grava em `logs/stale_trace.log` — **185 MB acumulados**):

| Estágio | Significado | Onde é emitido |
|---|---|---|
| **T1** | Linha SQT recebida (ts do recv) | `openfast_socket_adapter.py:376` |
| **T2** | Parse da linha concluído | `openfast_socket_adapter.py:377` |
| **T3** | Cache atualizado (`cache_ts=ver`) | `openfast_socket_adapter.py:393` |
| **T4** | `refresh()` entregou a chave via `_dirty_keys` | `openfast_socket_adapter.py:300` |
| **T5** | Leitura no provider (montagem da entrada) | `mercado_data_provider.py:_trace_t5` |
| **T6** | Estágio de cálculo (ctx/UC livre) | `stale_trace.log_t6`, ex.: `monitor_worker.py` `log_t6("monitor_geral_total", ...)` |

Ativação: `SH_TRACE_CHAVE=*` (tudo), `SH_TRACE_LIMIT_S=<s>` p/ auto-parada.

Atalho do pipeline: `monitor_worker.py:_processar_monitor_geral` → `MercadoDataProvider.capturar_dados_mercado()` (linha 565) → `refresh()` + varredura (Onda 1 + Onda 2).

---

## 3. Diagnóstico medido (dados REAIS de pregão, 10/08 13:59–14:07, 109.071 seq)

Extraído de `logs/stale_trace.log` (leitura stream, ~4s, via Python):

| Estágio | Mediana | p95 | Interpretação |
|---|---|---|---|
| T1→T2 (recv→parse) | ~imediato | — | socket ok |
| T1→T3 (recv→cache) | **1.5 ms** | 154 ms | **socket é RÁPIDO** — refuta a hipótese de gargalo no recv |
| T3→T4 (cache→refresh entrega) | **3.7 s** | 11.6 s (max 26.5s) | **delay principal** |
| `monitor_geral_captura` (T6) | 1.3 s (início) | degrada até **8–15 s** | varredura Onda 1/2 é o gargalo |

Log de 16:05 (sessão guiada, 15.841 instrumentos) — decomposição do ciclo de captura:

```
Varredura(F): monitor=16000 book=15870
  reg=0.168  (12% — registro/ondas)
  ref=0.023  ( 2% — refresh socket, RÁPIDO)
  var=1.408  (98% — varredura)  ← GARGALO
    onda2=1(0.000)  Onda 2/detalhes = ~0% (1 instrumento)
    onda1=15841(1.002)  ← ~71% do ciclo / 63µs por instrumento
  total=1.432
```

### Conclusões do porquê

1. **O socket não é o gargalo** (você tinha razão em desconfiar). Dado chega ao cache em ~2ms.
2. **O gargalo é a varredura (`capturar_dados_mercado`)**: Onda 1 percorre TODAS as ~15.8k chaves a
   cada ciclo e reconstrói a entrada (~20 campos) mesmo quando **nada mudou**.
3. **T3→T4 de 3.7s é consequência, não causa**: o `refresh()` do ciclo anterior já limpou
   `_dirty_keys`; o dado novo fica esperando o **próximo ciclo de varredura** (1.4s+ e degradando).
   Ou seja: o "delay na tela" = tempo do ciclo de varredura, não latência do feed.
4. **Degradação ao longo do dia (1.3s→15s)** = custo crescente de reconstruir `_dados_cache` e de
   contenção de mutex; cada ciclo reconstrói tudo mesmo sem mudança.

---

## 4. FIX APLICADO (mercado_data_provider.py) — 7 pontos confirmados

Verificado no arquivo (presente): 

1. **Gate de frescor desativado em push** — `_campo_stale`: `if suporta_push: return False`.
   Push change-driven = valor presente é a cotação atual (sem push = não mudou); saúde via
   `disponivel` (SYN ≤20s) + limpeza do cache na desconexão/reconexão. Nunca marca stale por idade.
2. **`_ler_campo_cache`/`_ler_campos` com `allow_stale=True`** quando `suporta_push and disponivel`.
3. **Corte STRIKE/PEX no push** — `_registrar_detalhes_completos` e `_registrar_instrumento`: para
   push não assinam `FieldName.STRIKE` (RTD/COM mantém).
4. **Strike canônico do banco em push** — `_ler_instrumento_cache` (Onda 2) e Onda 1 usam
   `inst.strike` (populado via API opcoes.net.br no import; 50.675/50.675 no banco).
5. **Batching Onda 1** — 3× `_ler_campos` (put/call/ativo; 1 lock por símbolo) no lugar de ~7
   leituras individuais (~12 locks → 3 locks por instrumento; ~190k → ~47k locks/ciclo).
6. **`_anotar_frescor`** — `idade_origem_ativo` derivada do `ts_origem_ativo` já lido (1 leitura de origem, não 2).
7. **Consumidores STRIKE preservados** (fix de regressão, aplicado nos 4):

| Arquivo | Linha | Mudança |
|---|---|---|
| `monitor_box.py` `_extrair` | antiga 63-72 | push → `inst.strike`; socket só como fallback |
| `monitor_put_ratio.py` `_extrair` | antiga 119-122 | push → `inst.strike`; socket só como fallback |
| `mpp_use_case.py` | 353-371 | push → `inst["strike"]`; campo `strike` adicionado ao mapa em `_obter_instrumentos_mapa` |
| `monitor_colares_calendario.py` | 178-184 | fallback (quando `dm is None`) → push usa `inst.strike` |

Padrão-origem seguido: `monitor_colares.py:293-300` (comentário: "PEX do servidor pode não ser o strike real").

### Validação executada
- `python -m py_compile` dos 5 arquivos → OK.
- Suíte completa: **663 passed (2×, 36.6s / 39.1s)** — antes e depois do fix dos consumidores.
- Medição real no socket (mercado aberto): SEM PEX = 68 seq/1.36KB vs COM PEX = 101 seq/2.03KB →
  **−33% bytes e −33% seq** no burst inicial (~48% PEX no trace completo).
- Strike ao vivo: `inst.strike` de `VALET159` (banco) = 15.96 == PEX do socket = 15.96 ✓.

---

## 5. Script de validação sem UI (para rodar amanhã no mercado aberto)

**Arquivo:** `scripts/validar_delay_amanha.py`
**Uso:** `python scripts/validar_delay_amanha.py --segundos 90 --ativos VALE3,PETR4`

O que faz:
- Conecta no FastTrade (127.0.0.1:557); assina ativos + 60 pares reais do banco (`instrumentos_base`).
- Instancia `MercadoDataProvider` e roda `capturar_dados_mercado()` em loop por `--segundos`.
- Imprime por ciclo: tempo de captura + nº de entradas.
- Relatório final: mediana/p95/max de `capturar_dados_mercado`, e T1→T3 / T3→T4 do trecho NOVO do
  `stale_trace.log` (usa offset inicial para não misturar os 185MB antigos — corrigido na sessão).
- Emite aviso se T3→T4 > 2s.

Correção aplicada nesta sessão: parâmetro `offset_inicio` em `_relatorio_t1_t4` (lê só o append novo).
Comportamento com mercado FECHADO: socket conecta e responde SYN, mas quase sem atualizações novas —
mede infra/ciclo; não mede delay real de cotação (precisa pregão aberto).

---

## 6. Plano para amanhã (mercado aberto 10:00–17:00) — VALIDAÇÃO + OTIMIZAÇÃO

### Validação (confirmar que o fix preserva as funcionalidades)
1. Rodar `scripts/validar_delay_amanha.py --segundos 300` com 3-4 ativos e comparar:
   - `capturar_dados_mercado`: deve manter **mediana < ~1.0-1.2s sem degradar** (não subir p/ 15s).
   - `T3→T4`: deve cair de 3.7s para perto do novo ciclo de varredura.
   - `T1→T3`: permanece ~2ms (sanity).
2. Rodar o app completo com `fonte_market_data=openfast` e confirmar que **BOX4P, MPP, PUT_RATIO,
   COLLAR_CAL e colares** populam as tabelas como antes (comparar com 16:05 de 10/08).
   Config.: `SH_TRACE_CHAVE=* SH_TRACE_LIMIT_S=300` por 5 min para comparar T1–T6 com o código novo.

### OTIMIZAÇÃO proposta (aplicar SÓ após confirmação — não aplicada ainda)
Mudança estrutural para atacar o porquê (varredura O(N) por ciclo):

1. **Skip de Onda 1 por dirty key** — em push, pular instrumentos cujo `ativo/cod_put/cod_call` não
   apareceu em `codigos_mudados` (já calculado na linha ~659 e usado só na Onda 2). Reconstruir
   entrada apenas para quem mudou.
2. **Reuso de `_dados_cache` na Onda 1** (mesma mecânica que a Onda 2 já tem nas linhas 709-774):
   se o instrumento não mudou, devolver a entrada anterior em vez de reconstruir os ~20 campos.
3. (Opcional) reduzir `t_status` re-agrupando as 3 leituras `ler_status_cache` num único
   `_ler_statuses` com 1 lock.

Meta: transformar o ciclo de captura de O(N=15.8k) completo para **O(#mudanças)**.

---

## 7. Observações / pendências / riscos

- **Higiene:** `_idade_origem_fonte` em `mercado_data_provider.py:159` ficou **órfã** (ninguém chama;
  idade agora derivada inline). **Não removida** (aguarda confirmação; remover é seguro, 1 método).
- `stale_trace.log` tem **185 MB** sem rotação — o usuário pediu limpeza de logs (já foi tema de
  desgaste na sessão). Candidato: apagar/rotacionar quando o diagnóstico T1–T6 terminar.
- `SH_TRACE_CHAVE`/`SH_TRACE_LIMIT_S` e o módulo `stale_trace.py` são temporários (docstring: "Remova após o diagnóstico").
- **Git:** working tree sujo com alterações não relacionadas (main.py, DTOs, logs, config) — o fix
  desta sessão é só em `mercado_data_provider.py` + 4 consumidores + script. Nada foi commitado.
- Banco de dados em `%APPDATA%/Spreadhunter/spreadhunter.db`, tabela `instrumentos_base` (não `instrumentos`).
- RTD/Profit intocado: `rtd_config.py:8` `RTD_CAMPO_STRIKE="PEX"`; `rtd_fast_trade.py:13` `_CAMPOS_SONDA=("PEX","LAST","BID","ASK")`.
- Mercado B3: seg-sex 10:00–17:00 (Brasília). Fora disso, RTD/OpenFast não retornam cotações.