# Regras de Negócio

## Strike de Opções

**NUNCA persista `strike` no banco de dados.** O strike de opções sofre ajustes
frequentes (ex-dividendo, desdobramento, grupamento). A única fonte confiável é o
RTD do Profit em tempo real. O campo `InstrumentoOpcional.strike` existe como
fallback opcional em memória, mas não deve ser lido/escrito no SQLite.

Se o RTD não fornecer strike em algum cenário, o sistema deve falhar ruidosamente
— não tentar adivinhar nem usar fallback do banco.

---

## Sessão 09/06/2026 — Correções Estruturais + Tuning Performance

### O que foi feito

#### Custos B3 (Crítico)
- **Base trocada**: todas as 5 calculadoras usavam `strike` como base para custos B3. Agora usam **prêmio da opção** (opções) e **preço da ação** (ações), conforme tarifário oficial da B3.
- **Ida-e-volta**: custos agora consideram entrada + saída (×2).
- **Collars**: perna de ação (`custos_stock`) estava ausente — agora incluída.
- `calculadora_custos_b3.py`: novos métodos `custos_opcao()`, `custos_stock()`, `taxa_total_stock()`.
- `calculadora_colar_calendario.py`: removido `max(pnl - custo, 0.0)` — perdas propagam corretamente.

#### SQLite PRAGMAs
- `synchronous=NORMAL`, `cache_size=-8000` (8MB), `temp_store=MEMORY` em `get_connection()`.

#### Performance — CAB Skip + Cache
- Wave 2 instruments leem só CAB (2 leitores). Se CAB não mudou, reusam `_dados_cache` e atualizam apenas status.
- Fast scan medido: **0.001–0.009s** (vs ~4.66s global scan inicial).
- `mercado_data_provider.py`: `_cab_anterior` + `_dados_cache`.

#### MPP — Root Cause + Desligamento
- **Gargalo real era MPP**: `calcular_instantaneo()` consumia 8s a cada ~10s. `RefreshData(0)` sempre foi 0.001s.
- `mpp_habilitado` agora lê do banco de dados (não hardcoded `True`).
- `_mpp_carga_completa`: MPP instantâneo só roda após Onda 1 terminar.
- Sinal `mpp_status_changed(bool)` emitido para UI.
- `mpp_dialog.py`: status indicator (🟢 Ativo / 🔴 Desligado).
- `parametros_widget.py`: `mpp_habilitado` (checkbox) + `mpp_instantaneo_interval` (spinbox) adicionados ao grupo BOX_4P.
- DB: `mpp_habilitado=0`, `mpp_instantaneo_interval=48`.

#### Ex-Dividendo — DisconnectData
- `invalidar_cache()` → `DisconnectData` + remove de `_topic_map`/`_topic_reverse`. `registrar_topico()` gera **novo topic ID**.
- `forcar_refresh_ex_dividendo()` limpa `_cab_anterior` + `_dados_cache`.

#### Book Detection — Correção Crítica
- **Race condition**: manutenção adicionava a `_chaves_com_book` (via `cabecalho_book > 0`), mas o scan removia no mesmo ciclo (`_ler_instrumento_cache` retornava None porque bid/ask/strike ainda não estavam no cache RTD). Resultado: "0 with book" permanentemente.
- **Fix 1**: scan NÃO remove mais de `_chaves_com_book` se o dado não chegou.
- **Fix 2**: `recarregar_parametros()` agora limpa `_chaves_detalhes_completos` + `_cab_anterior` + `_dados_cache` junto com `_chaves_com_book`, forçando re-detecção completa.
- **Fix 3**: background scan batch aumentado de 300 → 500 instrumentos por ciclo.
- **Fix 4**: manutenção mudada de %10 (25s) para %2 (5s).

#### Carga Inteligente — Bug Fix
- `perf_*` parâmetros nunca existiam no banco (carga inteligente, range, meses, dias mínimos). Seeded via `database.py`.
- Filtros DTE + strike range agora funcionam corretamente.

#### UI
- Tooltips em todas as colunas (monitor, box, collar, collar calendário, MPP).
- Ordem de colunas persiste entre sessões via QSettings (`column_utils.py`).
- `_colar_auto = False` (revertido após diagnóstico).
- MPP enable/disable + interval na tela de Parâmetros (grupo BOX_4P).

#### Correções anteriores mantidas
- Background scan corrigido (33k+ instrumentos).
- Filtros `viavel` removidos (cosmético apenas).
- Logs `Collar DIAG` / `Collar CALC`.
- TP.Op filter restaurado.
- Ganhos negativos propagam sem caps.
- IR split worst/best case no collar.

### Estado Atual (Fim da Sessão)
- **Performance**: ciclo ~0.001s (scan) + 0.3-0.6s (manutenção esporádica). MPP 0.000s.
- **Book detection**: após restart, leva 3-4 ciclos para cache RTD encher e books aparecerem.
- **Priority JSON**: `rtd_prioridade.json` é salvo com `_chaves_com_book`. Na próxima abertura, Onda 1 começa pelos que tinham book.
- **Filtros**: strike ±70%, DTE ≤6 meses, dias mínimos 10.
- **36k instrumentos totais**, ~3k após filtros, ~350 com book.

### Próximos passos (Próxima Sessão)
1. Rodar com Profit aberto em mercado para validar collares, boxes e performance final.
2. Verificar se books sobem corretamente após restart.
3. Se necessário: re-ativar MPP com intervalo maior (48+ ciclos ≈ 2min).
4. Se necessário: investigar fallback de strike via API B3 para dividendos overnight.

