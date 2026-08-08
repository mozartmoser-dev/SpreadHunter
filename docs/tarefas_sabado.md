# Tarefas de sábado — STALE OpenFast

**Status:** Fase 1 concluída (commit `ede0d65`) + refinamentos pronto-sessão NÃO commitados.
**Data da anotação:** 08/08/2026, fim de sessão (opencode fechado e reaberto).

---

## Onde paramos

### Feito e testado (Fase 1, commit `ede0d65`)

- Bloco de dado antigo do OpenFast gated por janela `stale_campo_s`.
- `is_stale_campo()` / idade dos campos no adaptador.

### Feito mas AINDA NÃO COMMITADO (na working tree)

- `mercado_data_provider.py`:
  - `_preco_ativo_cache_fresco()` — fallback de preço do ativo só dentro da janela de frescor (nunca valor velho p/ cálculo).
  - `_cont_stale_skip_ciclo` — contador por ciclo; log STALE acumulado por ciclo.
  - Entrada marcada `stale=True` quando não há preço fresco (bloqueia alimentação da calculadora).
- `openfast_socket_adapter.py`:
  - `verificar_conexao()` (watchdog) inválida o cache ao detectar thread leitora morta — nada ressuscita.
- `monitor_oportunidades.py`:
  - Fallback `vov_put/voc_call` quando `vov_put_boca/voc_call_boca` = 0.
- Testes novos: `test_perna_stale_nao_alimenta_e_retoma_com_push_novo`, `test_syn_nao_renova_idade_ask_bid`, `test_thread_morta_invalida_cache`.
- `config/parametros_default.json` e `backconfsh/configsh.json`: `fonte_market_data = "openfast"`.

Suíte completa: **643 passed** em ~94s.

## Validação ao vivo (sábado 08/08 — app `main.py` + OpenFast real)

Rodado ~5 min com `fonte=openfast` (porta 557, FastTrade aberto, hoje sábado sem pregão). **Resultado: 0 sinais com dado antigo.**

Evidências no log:
- **Gate STALE ativo:** a cada ciclo `OF STALE: ~37.7k entries ... não alimentaram a calculadora (janela 15.0s)` — acumulado milhões. Tudo idoso fica fora do cálculo. ✅
- **Nenhuma oportunidade gerada:** `PipelineTracker BOX/SBTH ... viaveis=0` em todos os ciclos. Nenhum sinal montado com cotação velha. ✅ (esperado: sábado não há push novo.)
- **`Re-registro OpenFast` rodando (50 ativos/ciclo)** — fluxo de reacord storm continuou normal.
- `book=` caiu de ~7000 (fim da Onda 1, refresh inicial) para ~300-530 nos ciclos seguintes — só o residual dentro da janela.
- Único `WinError 10038` no log pertence ao **encerramento da sessão do app anterior** (fechar a janela fecha o soquete) — não é da sessão atual.

### Para verificar segunda-feira (pregão)
- [ ] Confirmar que com push real os `book` voltam a subir e `viaveis` > 0 (feed ativo).
- [ ] Observar a RETOMADA: perna STALE (>15s) que recebe push novo volta a alimentar (o teste E2E `test_perna_stale_nao_alimenta_e_retoma` cobre; validar ao vivo).
- [ ] Acumulado STALE é monotônico (não zera) — só contagem de log, sem impacto no cálculo; decidir se quer reset por ciclo.

## Próximo passo imediato

[] Commitar o diff pendente (opcional; usuário já foi avisado).

## Fase 2 — o que falta (do `docs/plano_stale_openfast.md`)

1. **Interface `MarketDataSource.ler_campo_cache(..., allow_stale=False)`** + `is_stale_campo()`:
   - Replicar em Profit/RTD, FastTrade e mock, sem mudar contrato interno.
2. **Use cases/calculadoras:** descartar oportunidade se qualquer perna `stale` (regras de estratégia intactas).
   - Gate: `is_stale_campo()` em campo crítico (ASK/BID de perna, `preco_ativo`) ⇒ não é oportunidade agora.
3. **Parâmetros (BD-first):**
   - Chaves novas: `assinar_timestamp_openfast` (default 0), `absente` tolerância entre pernas `stale_sinal_s` (default 30).
   - Tocar: `config/parametros_default.json` + `parametro_operacional.py` (fallback) + `parametros_widget.py` + `regras_dialog.py`.
4. **`get_engine_stats`:** emitir `stale_count` / `feed_state`.
5. **Logs:** `STALE`, `DISCONNECTED`, `NO_NEW_UPDATE` (com `received_ts`, `cache_ts`, `stale_age`, `subscription_generation`, motivo).
6. **`forcar_leitura()`:** nunca devolver valor antigo no default (remover fallback `return old`); aguardar evento novo pós-chamada.

## Regras invariáveis (preservar em Fase 2)

- `SYN` NUNCA renova `_cache_ts` de ASK/BID (apenas `_ultimo_syn`/conectividade).
- TIME/TIMENEG só diagnóstico; nunca vira timestamp do ASK.
- Strike nunca persistido; `MOD` só de CALL; custos B3 por prêmio (×2); chave `ativo|cod_opcao`.