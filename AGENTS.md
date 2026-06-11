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

---

## Sessão 10/06/2026 — Gráfico de Candles (OpcoesNet)

### O que foi feito

#### Novo endpoint API
- **Request type descoberto**: `QuotesHistoryByAsset` com parâmetro `{timeframe: "Day", assets_ids: "PETR4"}` extraído do bundle `ui-bundle-after.js` do site opcoes.net.br
- **`OpcoesNetClient.get_stock_history()`**: método raw que chama a API e retorna dicionário com `data_fields` e `data_rows`
- **`OpcoesNetClient.get_stock_history_formatted()`**: método que parseia os campos (date, open, high, low, close, change, volume, vol_ewma, vol_impl) e retorna lista de dicts, limitada a 252 pregões (≈12 meses)

#### Botão "Ver Gráfico"
- Adicionado nos diálogos de detalhamento: `colar_dialog.py:_mostrar_detalhes` e `colar_calendario_dialog.py:_mostrar_detalhes`
- Posicionado ao lado do "📈 Ver Variação"

#### Gráfico (`_plot_historico`)
- **Subplot superior**: candles (barras OHLC) com cores verde/subida e vermelho/descida
- **Curva de Gauss horizontal**: distribuição normal dos retornos logarítmicos plotada sobre os preços, com linhas verticais nos níveis 1σ, 2σ, 3σ e preços anotados (ex: `1σ\nR$45.30`)
- **Subplot inferior** (se houver dados): volume normalizado (barras) + volatilidade histórica (blue) + implícita (red) em twin axis
- Layout escuro (`#0d0d0d`), figura 11×6.5

#### Arquivos modificados
- `src/infrastructure/integrations/opcoesnet_client.py`: +2 métodos (`get_stock_history`, `get_stock_history_formatted`)
- `src/ui/desktop/colar_dialog.py`: botão "📊 Ver Gráfico" + método `_plot_historico`
- `src/ui/desktop/colar_calendario_dialog.py`: botão "📊 Ver Gráfico" + método `_plot_historico`

### Próximos passos (Próxima Sessão)
1. Rodar com Profit aberto em mercado para validar collares, boxes e performance final.
2. Verificar se books sobem corretamente após restart.
3. Se necessário: re-ativar MPP com intervalo maior (48+ ciclos ≈ 2min).

---
## Sessão 10/06/2026 — Gráfico de Candles (OpcoesNet) — Finalizado

### O que foi feito
- `_plot_historico()`: candles OHLC (subplot superior) + volume/vol_hist/vol_impl (subplot inferior)
- Curva de Gauss: linhas sigma horizontais (1σ, 2σ, 3σ) com preços anotados na borda direita + mini-curva em inset no canto superior esquerdo (sigma baseado no DTE da operação, não fixo em 21)
- Linha do spot (preço atual do Profit) em ciano tracejado horizontal com rótulo "Spot R$XX.XX"
- Removido filtro `prices_arr.min() <= p <= prices_arr.max()` que cortava sigmas fora do range histórico — `set_ylim` agora inclui todos os níveis sigma
- Sigma period dinâmico: `colar_dialog` usa `max(5, int(r.dias * 5/7))`, `colar_calendario_dialog` usa `max(5, r.dte_call)`
- Corrigido bug que distorcia eixo X: removido bloco duplicado que tentava plotar preços (R$) sobre eixo de datas com `ax1.plot(x_price, ...)`
- Layout escuro (#0d0d0d), sem `tight_layout` (travava com gridspec + inset_axes)
- Testado com PETR4 offline — gráfico abre, fecha e renderiza corretamente
- Ambos os diálogos (`colar_dialog.py`, `colar_calendario_dialog.py`) corrigidos

---

## Regra Geral: Parametrização Obrigatória

**TODO valor numérico que represente uma condição de negócio (dias, percentuais,
limiares, timeouts, intervalos, margens) DEVE vir de um parâmetro no banco de
dados, NUNCA ficar hardcoded no código.**

Fluxo obrigatório para novos parâmetros:
1. `database.py` — seed `INSERT OR IGNORE`
2. `parametro_operacional.py` — `PARAMETROS_DEFAULT` com fallback
3. `parametros_widget.py` — entrada na UI + `PARAMETROS_INFO`
4. `regras_dialog.py` — template string para exibição no diálogo de regras
5. Use case / provider — ler via `repo.get_by_chave()` ou `_get_param()`
6. Se for parâmetro de calculadora, adicionar no construtor e passar do use case

Exceções permitidas apenas para constantes matemáticas (0.5, 100%), valores
estruturais (2 pernas, 1 ativo), ou tuning puramente cosmético (frequências
de som, timers de UI). Qualquer dúvida: parametrizar é mais seguro.

---

## Sessão 10/06/2026 — Collar Calendário + Correções (REVISAR NA PRÓXIMA)

### O que foi alterado (desfazer se não funcionar)

#### mercado_data_provider.py
- `capturar_dados_mercado()`: Onda 1 agora entra no `dados_mercado` com
  PEX/strike + OCP + OVD + ULT. QUL=0 sinaliza "não medido".

#### monitor_colares_calendario.py
- Filtros 6 e 7 (call OTM, put OTM) **removidos** — aceita qualquer strike
  relativo ao spot (ITM, ATM, OTM). O pareamento usa distância de strike
  (`calendario_strike_diff_max`) como único filtro direcional.
- Log temporário removido (estava entre filtro 5 e pareamento).

#### calculadora_colar_calendario.py
- Viabilidade (`viavel`) agora usa **PnL bruto** (antes de B3 e IR) em vez
  de PnL pós-B3. Custos são exibidos nas colunas para avaliação manual.

#### Parâmetros no banco (ambos SQLite: `data/` e `config/`)
| Chave | Valor | Descrição |
|---|---|---|
| `dte_call_min` | 25 | DTE mínimo para call vendida (dias corridos) |
| `dte_call_max` | 60 | DTE máximo para call vendida |
| `dte_extra_min` | 30 | Spread DTE mínimo put − call |
| `dte_extra_max` | 120 | Spread DTE máximo put − call |
| `dte_total_max` | 180 | DTE máximo total |
| `calendario_strike_diff_max` | 1 | Máx strikes de diferença entre Kc e Kp |
| `calendario_call_otm_max` | 0.15 | Não usado (filtro removido) |

### Resultado esperado
- Calls: qualquer opção com DTE 25-60 (mês 7 e semanais ≥ 25d)
- Puts: qualquer opção com DTE 61-180 (meses 8-11)
- Pares ordenados por proximidade de strike (não mais por OTM)
- Aproximadamente 4+ operações de calendário por ciclo

### Motivo das mudanças
- Filtros OTM engessavam viés direcional desnecessariamente
- Call OTM descartava calls ITM que ainda fazem calendário válido
- Put OTM descartava puts ITM que protegem melhor em quedas
- Viabilidade pós-B3 eliminava pares com custo marginal que valiam
  ser avaliados visualmente
- `dte_call_min` reduzido de 36→25 para capturar semanais longas
- `dte_extra_max` ampliado 90→120 para alcançar mês 11
- `dte_total_max` ampliado 120→180 para não cortar puts longas
- `calendario_strike_diff_max` reduzido 3→1 (mesmo strike)

