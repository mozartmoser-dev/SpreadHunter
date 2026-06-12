# Regras de Negócio

## Strike de Opções

**NUNCA persista `strike` no banco de dados.** O strike de opções sofre ajustes
frequentes (ex-dividendo, desdobramento, grupamento). A única fonte confiável é o
RTD do Profit em tempo real. O campo `InstrumentoOpcional.strike` existe como
fallback opcional em memória, mas não deve ser lido/escrito no SQLite.

Se o RTD não fornecer strike em algum cenário, o sistema deve falhar ruidosamente
— não tentar adivinhar nem usar fallback do banco.

## MOD (tipo_opcao) — Só da CALL

PUTs na B3 são sempre Europeias (`E`). Apenas CALLs podem ser Americanas (`A`).
Em `importflash.py` (⚡ Importar), `tipo_opcao` no banco deve vir do `r["mod"]`
**apenas quando `r["tipo"] == "CALL"`**. PUT não sobrescreve.

## Parametrização Obrigatória

**TODO valor numérico de negócio** (dias, percentuais, limiares, timeouts,
intervalos, margens) DEVE vir de um parâmetro no banco, NUNCA hardcoded.

Fluxo: `database.py` (seed) → `parametro_operacional.py` (defaults)
→ `parametros_widget.py` (UI) → `regras_dialog.py` (exibição)
→ use case/provider lê com `repo.get_by_chave()`.

Exceções: constantes matemáticas (0.5, 100%), valores estruturais (2 pernas),
cosmética (sons, timers UI).

---

## Sessão 09/06/2026 — Correções Estruturais + Performance

### Custos B3 (Crítico)
- Base trocada de strike → **prêmio da opção / preço da ação** conforme tarifário B3.
- Ida-e-volta (×2). Collar: perna de ação incluída.
- `calculadora_colar_calendario.py`: removido `max(pnl - custo, 0.0)`.

### Performance
- SQLite: `synchronous=NORMAL`, `cache_size=-8000`, `temp_store=MEMORY`.
- CAB skip: se CAB não mudou, reusa `_dados_cache`.
- MPP: `mpp_habilitado` no banco (default 0). Instantâneo só após Onda 1.

### Book Detection
- Scan NÃO remove de `_chaves_com_book` se dado RTD não chegou.
- `recarregar_parametros()` limpa todos os caches → re-detecção completa.
- Manutenção a cada ~5s (%2), batch de 500.

### Carga Inteligente
- `perf_*` parâmetros seeded via `database.py`.
- Filtros DTE + strike range funcionando.

### UI
- Tooltips em todas as colunas. Ordem de colunas via QSettings (`column_utils.py`).

---

## Sessão 10/06/2026 — Gráfico de Candles (OpcoesNet)

- `OpcoesNetClient.get_stock_history()` + `get_stock_history_formatted()` via API
  `QuotesHistoryByAsset` (timeframe=Day).
- Botão "📊 Ver Gráfico" em colar_dialog e colar_calendario_dialog.
- Subplot superior: OHLC candles + curva de Gauss sigma (1σ, 2σ, 3σ) + spot.
- Subplot inferior: volume + vol_hist (blue) + vol_impl (red).
- Sigma period dinâmico: `max(5, int(r.dias * 5/7))` (colar) / `max(5, r.dte_call)` (calendário).
- Layout escuro (#0d0d0d).

---

## Sessão 10/06/2026 — Collar Calendário

- **Filtros OTM removidos** — aceita calls/puts ITM/ATM/OTM. Pareamento por
  distância de strike (`calendario_strike_diff_max=1`).
- Viabilidade usa **PnL bruto** (pré-B3/IR). Custos exibidos para avaliação.
- Parâmetros: `dte_call_min=25`, `dte_call_max=60`, `dte_extra_min=30`,
  `dte_extra_max=120`, `dte_total_max=180`.

---

## Sessão 11/06/2026 — API OptionsChain + Semanais + Crash Fix

### Semanais via API
- `fetch_all_options()` migrado de HTML da matriz → API `OptionsChain`.
- Retorna **todas as séries** (mensais + W1/W2/W3/W4). PETR4: 1.092 → 4.516 opções.

### Crash ao arrastar coluna
- `atualizar_resultados()`: congela `sectionsMovable(False)` + `blockSignals(True)`
  durante `beginResetModel()/endResetModel()`.
- `column_utils.py`: `salvar_ordem_colunas()` e `restaurar_ordem_colunas()` em `try/except`.

---

## Sessão 11/06/2026 (parte 2) — MOD fix + Cleanup + Blacklist

### MOD fix no importflash
- `importflash.py` (⚡ Importar) também só lê `mod` das CALLs — PUTs nunca sobrescrevem.
- Antes estava lendo de qualquer um (PUT vencia por ordem no loop), deixando quase tudo `E`.

### Cleanup
- Menu **Arquivo > Importar do Opcoes.Net.Br...** removido (use case `importar_base_opcoesnet.py` deletado)
- Menu **Arquivo > Importar de planilha XLSX...** removido (use case `importar_base.py` + dialogs deletados)
- Só resta **⚡ Importar** (`importflash.py`)
- `ExcelImporter` removido de `excel_importer.py`; utilitários (`extrair_strike`, etc.) mantidos

### Blacklist
- Adicionados 37 BDRs (`*34`) + BOVA11 + 6 ativos sem opções via scan
- Agora 53 ativos na blacklist (`black_list_import`)
- 247 ativos disponíveis na API → 194 importados efetivamente

### Final
- 47.862 registros (33.105 A, 14.757 E) → após remover preservação: 43.958 (30.464 A, 13.494 E)
- 140/140 testes passando
- `instrumentos_base.csv` exportado para Desktop

---

## Sessão 11/06/2026 (parte 3) — RTD Timeout + COM Thread Safety + Blacklist Final

### PERF-001: Rate Limiter no RTD RefreshData
- `RTDProfit.refresh(timeout_ms)` usa timestamp gate: se o último `RefreshData(0)` ocorreu
  há menos de `timeout_ms`, pula o ciclo (retorna vazio). Chamada é **síncrona** na thread
  do worker — sem threading COM para evitar `RPC_E_WRONG_THREAD`.
- Parametrizável via `rtd_refresh_timeout_ms` (seed=5000ms, 0=sem limite = toda ciclo)
- Visível em Parâmetros > Geral

### Blacklist sem preservação
- Ativos na blacklist são removidos do banco na importação (sem `preservados`)
- BOVA11 e BDRs somem da tabela `instrumentos_base`

### Final
- 43.958 registros (30.464 A, 13.494 E) — 194 ativos, 53 blacklist
- 146/146 testes passando

---

## Sessão 11/06/2026 (parte 4) — Crash ao Arrastar Coluna (Segfault C++)

### Causa
Conflito C++ no Qt entre `sectionMoved` (drag) e `layoutChanged` (sort) quando ambos habilitados (`setSortingEnabled=True` + `setSectionsMovable=True`). O clique no header acionava sort e drag concorrentemente, e o handler `salvar_ordem_colunas()` acessava `logicalIndex` durante layout inconsistente → segfault.

### Correção
Substituir chamada direta no `sectionMoved` por `QTimer.singleShot(0, lambda: ...)`:

```python
header.sectionMoved.connect(
    lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header, "key"))
)
```

O delay de 0ms posterga a execução para o próximo ciclo do event loop, após sort/drag estarem completamente finalizados.

### Arquivos alterados
- `src/ui/desktop/colar_dialog.py:482`
- `src/ui/desktop/colar_calendario_dialog.py:393`
- `src/ui/desktop/box_dialog.py:8,313`
- `tests/test_column_crash.py` — 6 testes novos

### Testes
146/146 passando (140 + 6 novos).

---

## Auto-documentação dos Filtros nas Regras

A ordem dos filtros é declarada como constante (`FILTROS_COLLAR_CALENDARIO`,
`FILTROS_COLAR`) no próprio use case. O `regras_dialog.py` importa dinamicamente
e exibe sem duplicação manual.

Arquivos fonte:
- `src/application/use_cases/monitor_colares_calendario.py` (linha 20)
- `src/application/use_cases/monitor_colares.py` (linha 20)
- `src/ui/desktop/regras_dialog.py` (import nas linhas 12-22, exibição em `_montar_regras_codigo`)

Para adicionar filtros a uma nova estratégia, basta criar a constante no use case
e registrá-la em `_FILTROS_POR_ESTRATEGIA` no `regras_dialog.py`.

---

## Pendente: Migração PyQt5 → PySide6 (desbloqueia Python ≥3.12)

- PyQt5 5.15.11 é EOL e não roda em Python ≥3.12.
- PySide6 tem API ~idêntica, é mantido ativamente.
- Migração mecânica: trocar imports + ajustar enums (estilo, alinhamento, cores).
- Fazer na próxima sessão, se quiser. Depois instalar Python 3.12/3.13 + re-instalar libs.
