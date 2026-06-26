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

## Sessão 16/06/2026 — Migração PyQt5 → PySide6 ✅

- PySide6 6.11.1 instalado, PyQt5 removido das dependências.
- Migração completa: 23 arquivos .py com imports, enums, pyqtSignal, QVariant.
- `QAction` movido de `QtWidgets` para `QtGui`.
- `pyproject.toml`: `PyQt5>=5.15` → `PySide6>=6.5`.
- 159/159 testes passando, app inicializando sem erros.
- Python 3.11.0 → **Python 3.13.14** (upgrade concluído).
- Próximo passo opcional: testar matplotlib com PySide6 backend — pode melhorar renderização de gráficos.

---

## Stack atual (16/06/2026)

| Ferramenta | Versão | Instalação |
|------------|--------|-----------|
| **Python** | 3.13.14 | `C:\Program Files\Python313\python.exe` |
| **PySide6** | 6.11.1 | pip |
| **pywin32** | 312 | pip (DLLs em `pywin32_system32`) |
| **scipy** | 1.17.1 | pip |
| **numpy** | 2.4.6 | pip |
| **matplotlib** | 3.11.0 | pip |
| **requests** | 2.34.2 | pip |
| **beautifulsoup4** | 4.15.0 | pip |
| **psutil** | 7.2.2 | pip |
| **openpyxl** | 3.1.5 | pip |
| **python-dotenv** | 1.2.2 | pip |
| **pytest** | 9.1.0 | pip |

Python 3.11.0 ainda presente em `C:\Users\Mozart\AppData\Local\Programs\Python\Python311\` como fallback.

---

## Horário do Mercado

B3 — Segunda a Sexta, **10:00 às 17:00** (horário de Brasília). Fora desse horário não há dados RTD do Profit, então scans não retornam oportunidades.

---

## Sessão 17/06/2026 — Correções do novaavaliacao.md (11 itens)

### Fixes aplicados

| # | Item | Arquivo | Mudança |
|---|------|---------|---------|
| 1 | BUG-002 | `monitor_colares_calendario.py:164` | Filtro de liquidez: rejeita se QUL≤0 em ambas pernas |
| 2 | FIN-006 | `mpp_use_case.py:432,596` | `r_cont = log(1+r)` na paridade contínua; `_calcular_fator_premio_cdi` aceita `r_cont` |
| 3 | BUG-007 | `database.py:16` | `threading.local` usa `hashlib.md5` do path (evita `AttributeError` com `\` e `:`) |
| 4 | FIN-003 | `calculadora_colar_calendario.py:300-331` | `capital_base = abs(capital)` p/ denominador; `risco_max` não zera; `credito_ratio` no monitor |
| 5 | FIN-001+BUG-001 | `calculadora_colar.py:160,213` | Pior retorno = sempre `strike_put`; melhor = sempre `strike_call` |
| 6 | BUG-004 | `mpp_use_case.py:667-673` | DELETE loop por código (correlated subquery não funciona no SQLite) |
| 7 | BUG-008 | `calculadora_colar.py:240-250` | `pop_upside` usa `iv_call`, `pop_downside` usa `iv_put` (sem `sigma_medio`) |
| 8 | BUG-009 | `monitor_colares.py:295-321` | Score normaliza apenas viáveis; `max_cdi` não poluído por inviáveis |
| 9 | BUG-010 | `calculadora_colar_calendario.py:197,225` | `if be_baixa` → `if be_baixa is not None` (evita falso None se 0.0) |
| 10 | — | `calendario_b3.py:57,65` | `np.busday_count` encapsulado em try/except p/ datas não-úteis (crash fim de semana) |
| 11 | — | `mpp_use_case.py:814-818` | Snapshot counter inicia em 1 e só salva a cada `SNAPSHOT_INTERVAL` ciclos |

## Sessão 24/06/2026 — Correções Deploy + RTD Estável

### Database path (crítico para deploy)

**NUNCA use path hardcoded.** O banco DEVE ficar em `%APPDATA%/Spreadhunter/spreadhunter.db`
para persistir entre atualizações. Função `get_db_path()` em `database.py`:

```python
def get_db_path() -> Path:
    return Path(os.environ["APPDATA"]) / "Spreadhunter" / DB_NAME
```

**Migração automática**: na primeira execução, copia o banco antigo de `config/` para
`%APPDATA%/` sem deletar o original (`_migrar_banco_legado()` em `database.py:28`).

### importflash.py — path do banco

**NUNCA use `PROJECT_DIR / "config" / "spreadhunter.db"`.** Sempre importe e use
`get_db_path()` de `database.py`. Path hardcoded quebra no .exe compilado (PyInstaller
resolve `__file__` para temp dir). Arquivo: `scripts/validar_opcoes/importflash.py:22`.

### Import roda em QThread (não QProcess)

`QProcess` com `sys.executable` **não funciona** no .exe compilado (não há Python para
chamar). O import agora roda em `QThread` interno via `_ImportThread` em
`main_window.py:735`. Output vai para stdout do processo principal.

### RTD não fica flickando ON/OFF

Removido o `rtd_status.emit(False)` baseado em `dados_stale` em
`monitor_worker.py:378-383`. O status do RTD agora reflete apenas se `Dispatch` COM
funcionou — não se `RefreshData` retornou dados (já que `ServerStart` crasha sem Profit).

### Erro `name 'logger' is not defined`

Pode ocorrer no PyInstaller se `__name__` no logger não corresponder ao módulo real.
Garantir `logger = logging.getLogger(__name__)` no topo do arquivo (linha 18 em
`monitor_worker.py`). Se persistir, usar `logging.getLogger()` sem argumento.

### Build e Deploy

```powershell
# 1. Testar localmente — NUNCA pule esta etapa
python -m pytest tests/ -x -q --tb=short

# 2. Build
python -m PyInstaller --clean --distpath "$env:USERPROFILE\Desktop\dist" --workpath "$env:USERPROFILE\Desktop\build_pyi" spreadhunter.spec

# 3. Backup .env antes de remover
$envPath = "$env:USERPROFILE\Desktop\Spreadhunter\.env"
if (Test-Path $envPath) { Copy-Item $envPath "$env:USERPROFILE\Desktop\.env.spreadhunter.bak" }

# 4. Substituir deploy antigo
Remove-Item -Recurse -Force "$env:USERPROFILE\Desktop\Spreadhunter"
Move-Item "$env:USERPROFILE\Desktop\dist\Spreadhunter" "$env:USERPROFILE\Desktop\Spreadhunter"

# 5. Restaurar .env
if (Test-Path "$env:USERPROFILE\Desktop\.env.spreadhunter.bak") {
    Copy-Item "$env:USERPROFILE\Desktop\.env.spreadhunter.bak" $envPath
    Remove-Item "$env:USERPROFILE\Desktop\.env.spreadhunter.bak"
}

# 6. Limpar artefatos
Remove-Item -Recurse -Force "$env:USERPROFILE\Desktop\dist", "$env:USERPROFILE\Desktop\build_pyi"

# 7. Recriar INSTRUCOES.txt
@"
╔══════════════════════════════════════════════════════╗
║             SPREADHUNTER — INSTRUCOES              ║
╚══════════════════════════════════════════════════════╝

1. Renomeie .env.example para .env e edite com seu CPF e
   senha do site opcoes.net.br

2. Execute Spreadhunter.exe

3. Clique em ⚡ Importar (aguarde ~1-2 minutos)

4. Clique em Iniciar Monitoramento

5. Pronto! As oportunidades aparecerão nas abas:
   - Colar Protetivo
   - Colar Calendário
   - Box 4P

┌─────────────────────────────────────────────────────┐
│ Para alterar parametros: Menu > Arquivo > Parametros │
└─────────────────────────────────────────────────────┘
"@ | Out-File -Encoding utf8 "$env:USERPROFILE\Desktop\Spreadhunter\INSTRUCOES.txt"

# 8. Recriar .env.example
@"
# Credenciais opcoes.net.br
OPCOESNET_CPF=SEU_CPF_AQUI
OPCOESNET_SENHA=SUA_SENHA_AQUI
"@ | Out-File -Encoding utf8 "$env:USERPROFILE\Desktop\Spreadhunter\.env.example"
```

### Observações importantes p/ sessões futuras

- **Box 4P (`calculadora_box.py:87`)**: fórmula `lucro = clr - distancia` está **correta** — é um short box. Não inverter.
- **Performance**: várias escolhas de design são intencionais (conexões abrindo/fechando, O(n²) em listas pequenas, `except Exception: pass` em não-críticos). Não "corrigir" sem confirmar.
- **Testes**: 285/285 passando em todas as batidas (24/06).
- **Stack atual**: Python 3.13.14, PySide6 6.11.1, numpy 2.4.6, scipy 1.17.1, matplotlib 3.11.0, Pillow 12.2.0.

### Build — Hidden Imports obrigatórios no `.spec`

Sempre que adicionar uma lib nova, verificar se ela precisa estar em `hiddenimports` no `spreadhunter.spec`.
Libs já mapeadas (NÃO remover):

- **PIL/Pillow**: matplotlib `colors.py` depende de `PIL` e `PIL._tkinter_finder`. Não colocar em `excludes`.
- **matplotlib.backends.backend_qtagg**: necessário para gráficos em dialogs PySide6.
- **win32com/pythoncom/pywintypes**: RTD Profit (COM).
- **scipy.stats / scipy.optimize**: cálculos de volatilidade e MPP.

Se um gráfico der `ModuleNotFoundError` no .exe mas funcionar no código fonte, é hidden import faltando no `.spec`.
- **Deploy sempre pela pasta `C:\Users\Mozart\Desktop\Spreadhunter\`**.

---

## Sessão 26/06/2026 — Chave Composta (Layer 4) + Correção Cruzamento Ativos

### Problema
Códigos de opção **não são únicos entre ativos** na B3. PETR3 e PETR4 podem ter
opções com o mesmo código (ex: PETRH36) em séries diferentes. O sistema usava
`cod_put` como chave única → `inst_map` sobrescrevia um pelo outro → cruzava
ativos nas estruturas (ex: montava collar de PETR4 com opção de PETR3).

### Causa raiz
O código da opção B3 = 4 letras (empresa) + 1 letra (série: A-L CALL, M-Z PUT)
+ strike. **Não há letra de classe** (ON vs PN) no código. A única forma de
saber o ativo-objeto é pelo cadastro (DB / API).

### Correção — Chave Composta `(ativo, cod_opcao)`

Toda chave interna do pipeline agora leva o par `(ativo, cod_put)`:

| Estrutura | Antes | Depois |
|-----------|-------|--------|
| `inst_map` (`get_all_mapped()`) | `{cod_put: Instrumento}` | `{(ativo, cod_put): Instrumento}` |
| `_chaves_registradas` | `set{cod_put}` | `set{"PETR4\|PETRU36"}` |
| `_chaves_com_book` | `set{cod_put}` | `set{"PETR4\|PETRU36"}` |
| `_chaves_detalhes_completos` | `set{cod_put}` | `set{"PETR4\|PETRU36"}` |
| `_dados_cache` | `dict{cod_put: dados}` | `dict{"PETR4\|PETRU36": dados}` |
| `_cab_anterior` | `dict{cod_put: cab}` | `dict{"PETR4\|PETRU36": cab}` |
| `dados_mercado` (output) | `dict{cod_put: dados}` | `dict{"PETR4\|PETRU36": dados}` |

Onde `cod_put` = código da PUT (série M-Z). Use `f"{inst.ativo}|{inst.cod_put}"`.

### Arquivos alterados
- `src/infrastructure/persistence/repositories/repositories.py:105-115`
- `src/infrastructure/providers/mercado_data_provider.py` (todo)
- `src/infrastructure/providers/mock_market_data.py`
- `src/application/use_cases/monitor_colares.py:86-88`
- `src/application/use_cases/monitor_colares_calendario.py:127-135, 279-287`
- `src/application/use_cases/monitor_oportunidades.py` (loop + vetorizado numpy)
- `tests/test_fase3.py`, `tests/test_fase4.py`

### Lições Aprendidas
- **NUNCA** usar o 5º caractere do código da opção como "classe do ativo".
  A-L = CALL, M-Z = PUT. Não há indicador de ON/PN no código.
- A API do opcoes.net.br retorna `opt[4]` = moneyness (I=ITM, O=OTM), irrelevante.
- `opt[1]` = sempre 0, descartável.
- A única fonte confiável do vínculo opção→ativo é o banco (`instrumentos_base`).
- A chave composta é obrigatória como defesa em profundidade: se o mesmo código
  entrar para dois ativos diferentes, o sistema nunca os confunde.

### Pendência
- Validar se a persistência de prioridades (`_prioridade_set`) precisa de
  migração do formato antigo (só `cod_put`) para composto (`ativo|cod_opcao`).
  Atualmente carrega com fallback (tenta ambos).
- 355/355 testes passando.

---

## Pendência — Validação do calendário de DU no Black-Scholes

Testar se o Profit Pro usa **DC->DU exato (com feriados)** ou **aproximado (252/365)**
para o `T` no cálculo de IV e gregas.

**Como testar:**
1. Pegar um papel com vencimento conhecido
2. Ver o IV que o Profit mostra
3. Calcular IV próprio com `T_exato = dc_to_du_exato(hoje, venc) / 252` vs
   `T_aproximado = dc_to_du_aproximado(dte) / 252`
4. Ver qual valor bate com o do Profit

Se o Profit usar exato, vale migrar as calculadoras de spread (colar, calendário,
box) para usar `dc_to_du_exato(hoje, inst.vencimento)` em vez de
`dc_to_du(None, None, dias)`.
