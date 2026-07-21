# Spreadhunter — Regras para Agentes

Varredura de oportunidades em opções B3 (colar, collar calendário, box, MPP, taxa, SBTH vendida). Desktop Python/PySide6, SQLite, RTD via COM do Profit, API opcoes.net.br. **Windows-only.** Sem CI; testes rodam localmente.

## Confirmação obrigatória

**NUNCA aplique alterações sem antes apresentar a proposta e obter confirmação explícita** (use `question`). Fluxo: proposta → confirmação → execução.

## Comandos essenciais

```powershell
python -m pytest tests/ -x -q --tb=short            # todos
python -m pytest tests/domain/test_calculadora_cauda_assincrona.py -q
python -m pytest tests/test_fase3.py::TestX::test_y -q
python main.py                                       # dev
python -m pip install -r requirements.txt            # instalar dependências
python -m PyInstaller --clean --distpath "$env:USERPROFILE\Desktop\dist" `
  --workpath "$env:USERPROFILE\Desktop\build_pyi" spreadhunter.spec
```

Stack: Python 3.13.14, PySide6 6.11.1, sqlite3 (stdlib), scipy, numpy, matplotlib, pywin32, pillow, opencv-python, requests, python-dotenv, pyautogui, psutil, pytest, yfinance. `pyproject.toml` seta `pythonpath = ["."]` (imports from root). `requirements.txt` pinado. Pinos detalhados em `.opencode/skills/spreadhunter/SKILL.md` (carregue `skill spreadhunter`).

## Arquitetura não-óbvia

- `monitor_worker.py` em `src/ui/desktop/` (QThread que coordena use cases via sinais PySide6)
- Bootstrap: `src/infrastructure/persistence/bootstrap.py` → `main.py`
- `_ImportThread` em `grade_opcoes_dialog.py` (não em `main_window.py`)
- Fonte alternativa de dados: `src/infrastructure/providers/openfast_socket_adapter.py` (socket TCP, sem COM) — config `fonte_market_data=openfast` no banco
- `.env` contém credenciais opcoes.net.br — `.gitignore` já exclui, nunca commitar
- DB em `%APPDATA%/Spreadhunter/spreadhunter.db` via `get_db_path()` — nunca hardcoded

## Regras de negócio (resumo; detalhes em SKILL.md)

1. **Strike NUNCA persistido.** Vem do RTD em tempo real. Se RTD não fornecer, falhar. NUNCA extrair do sufixo B3 (`G445` ≠ 44.50).
2. **MOD (`tipo_opcao`) só da CALL.** PUTs B3 são Europeias (`E`). Ler `r["mod"]` apenas quando `r["tipo"] == "CALL"`.
3. **Parametrização obrigatória do banco.** TODO valor de negócio via `repo.get_by_chave()`. Nunca hardcoded. Fluxo: `database.py` (seed) → `parametro_operacional.py` → `parametros_widget.py` → `regras_dialog.py`. Ao adicionar parâmetro, tocar **todos** esses pontos + `config/parametros_default.json`.
4. **Custos B3** usam prêmio/preço (NUNCA strike). Ida-e-volta (×2).
5. **Chave composta `(ativo, cod_opcao)`.** Toda cache/mapa usa `f"{ativo}|{cod}"`. Códigos B3 não são únicos entre ativos.
6. **Coerência do book:** quem vende recebe `bid_*`, quem compra paga `ask_*`. `of_venda_*` = ASK (você paga); `of_compra_*` = BID (você recebe). Comprar ativo: paga `of_venda_ativo` (ask). **Taxa**: `receb = bid_ativo − ask_call`. **BOX Vendida**: `receb = bid_ativo + bid_put − ask_call`. **SBTH Vendida**: `receb = bid_ativo + bid_put`. **Collar**: `preco_compra_ativo` = `of_venda_ativo`.
7. **Box 4P** (`calculadora_box.py`): `lucro = clr - distancia` — short box, não inverter.
8. **Blacklist** (`black_list_import`): 53 ativos removidos na importação, sem preservação.
9. **Importador único:** `scripts/validar_opcoes/importflash.py` (⚡ Importar). API `OptionsChain` para todas as séries (mensais + W1-W4).
10. **BWB (Broken Wing Butterfly):** proteção de cauda do Collar Calendário com custo próximo de zero. Estrutura: corpo (2 vendidas no meio do strike) financia asas (1 comprada em cada ponta). **Alvo = breakeven da estrutura com ratio** (NUNCA 2σ fixo). Se custo da BWB > 40% do ganho extra do collar → inviável, não forçar. Detalhes: `pendenciascalendario.md`.

## Operação B3

Mercado B3: seg-sex **10:00–17:00** (horário de Brasília). Fora disso RTD do Profit não retorna dados. Testar com cotação dummy ou mock.

## Windows / PyInstaller gotchas

- **Import em QThread** (`grade_opcoes_dialog.py:_ImportThread`), não QProcess — `sys.executable` falha no .exe.
- **`hiddenimports` do `spreadhunter.spec` obrigatórios.** Já mapeados: `PIL`, `PIL._tkinter_finder`, `matplotlib.backends.backend_qtagg`, `scipy.stats`, `scipy.optimize`, `win32com`, `pythoncom`, `pywintypes`, `tzdata`, `cv2`, `win32api`, `win32con`, `win32gui`, `win32process`. Sintoma de falta: `ModuleNotFoundError` no .exe mas funciona no fonte. **PIL/Pillow não vai em `excludes`** (matplotlib depende).
- **COM thread safety**: `CoInitializeEx(COINIT_APARTMENTTHREADED)` no início de `MonitorWorker.run()`. `refresh(timeout_ms)` síncrono na thread do worker. Timeout: `rtd_refresh_timeout_ms` (seed 5000ms).
- **`runtime_hook.py`** em `scripts/` seta `MPLBACKEND` e adiciona `pywin32_system32` ao PATH do DLL.

## UI / Qt

- **Segfault ao arrastar coluna:** Qt conflita `sectionMoved` (drag) + `layoutChanged` (sort). Sempre usar `QTimer.singleShot(0, lambda: ...)` no handler. **Exceções (potenciais bugs):** `main_window.py:364` e `mpp_dialog.py:94` — evitar tocar sem corrigir.
- Em `atualizar_resultados()`: `sectionsMovable(False)` + `blockSignals(True)` durante `beginResetModel()`/`endResetModel()`.
- **Persistência de colunas** via QSettings em `column_utils.py`. Testes em `tests/test_column_crash.py`.
- **Filtros auto-documentados** no próprio use case (`FILTROS_COLAR`, `FILTROS_COLLAR_CALENDARIO`). `regras_dialog.py` importa dinamicamente via `_FILTROS_POR_ESTRATEGIA`.
- **`ParametrosWidget`**: sidebar (QListWidget) + QStackedWidget, ordem fixa `_SIDEBAR_ORDER`. QSettings persiste `parametros/last_section`.

## Pipeline (worker)

`monitor_worker.py` ciclo principal: 1. Geral → 2. Colar → 3. Collar Calendário → 4. Box 4P → 5. Manutenção → 6. Reconexão → 7. MPP. Onda 2: `_processar_otimizado()` → `CalculadoraCaudaAssincrona.processar_otimizado()` → persiste em `historico_simulacoes`.

**`_flush_buffer` (crítico):** em `mercado_data_provider.py` — sempre que mexer em `_registrar_batch_inteligente()` ou `capturar_dados_mercado()`, TODOS os branches devem chamar `self._flush_buffer()`. Esquecer → opções nunca assinadas → book=0 mesmo com FAST conectado.

**Performance:** `threading.local` pool SQLite (key = `hashlib.md5(path)`); PRAGMAs: `synchronous=NORMAL`, `cache_size=-8000`, `temp_store=MEMORY`, `journal_mode=WAL`, `foreign_keys=ON`. Book scan não remove de `_chaves_com_book` se RTD não chegou. `recarregar_parametros()` limpa todos os caches. Manutenção ~5s (%2), batch 500. `mpp_habilitado` default 0. CAB skip se não mudou → reusa `_dados_cache`.

## Refatoração: crítico vs. rotineiro

**Crítico** (mexer com cuidado): `monitor_worker.py`, `monitor_colares_calendario.py`, `calculadora_*.py`, `calculadora_cauda_assincrona.py`, `database.py`, `repositories.py`, `parametro_operacional.py`, `main_window.py`.

**Rotineiro** (sem impacto em cálculo/dados): tests, dialogs, models de tabela, tooltips, parâmetros, cores, `column_utils.py`, `regras_dialog.py`, filtros, labels.

## Referências

- `.opencode/skills/spreadhunter/SKILL.md` — use `skill spreadhunter` para regras completas + histórico
- `.opencode/plugins/graphify.js` — knowledge graph em `graphify-out/`; use skill graphify em vez de grep crus
- `docs/DISTRIBUICAO.md`, `docs/pnt_importacao.md` — deploy/PNT
- `pendenciascalendario.md` — diagnóstico BWB + simulações
- `planoprotecaocauda.md` — planejamento de proteção de cauda
- `INSTRUCOES_AMIGO.txt` — diagnóstico .exe
