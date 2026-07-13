# Spreadhunter — Regras para Agentes

Varredura de oportunidades em opções B3 (colar, collar calendário, box, MPP, taxa, SBTH vendida). Desktop Python/PySide6, SQLite, RTD via COM do Profit, API opcoes.net.br. **Windows-only.** Sem CI; testes rodam localmente.

## Confirmação obrigatória

**NUNCA aplique alterações sem antes apresentar a proposta e obter confirmação explícita** (use `question`). Fluxo: proposta → confirmação → execução.

## Comandos essenciais

```powershell
python -m pytest tests/ -x -q --tb=short            # todos
python -m pytest tests/test_calculadora_cauda_assincrona.py -q
python -m pytest tests/test_fase3.py::TestX::test_y -q
python main.py                                       # dev
python -m PyInstaller --clean --distpath "$env:USERPROFILE\Desktop\dist" `
  --workpath "$env:USERPROFILE\Desktop\build_pyi" spreadhunter.spec
```

Stack: Python 3.13.14 (`C:\Program Files\Python313\python.exe`), PySide6 6.11.1, sqlite3 (stdlib), scipy 1.17.1, numpy 2.4.6, matplotlib 3.11.0, pywin32 312, pytest 9.1.0. **442 testes**. `pyproject.toml` seta `pythonpath = ["."]` (imports from root). `requirements.txt` pinado.

## Estrutura

```
src/application/use_cases/        monitor_*, mpp_use_case, exportar_operacao, coletar_taxas_aluguel
src/application/dtos/             dtos.py, dtos_venda_coberta.py, dtos_vendida.py
src/application/services/         workspace_service.py
src/domain/entities/              instrumento_opcional, parametro_operacional, oportunidade, taxa_aluguel, …
src/domain/services/              calculadoras, calendario_b3, pipeline_tracker, elegibilidade, montadora_box, market_data_source
src/domain/rules/                 classificacao_oportunidade.py
src/infrastructure/integrations/  opcoesnet_client.py, investsite_client.py, pnt.py
src/infrastructure/persistence/   database.py (SQLite + PRAGMAs + seed params)
src/infrastructure/persistence/repositories/  repositories.py, workspace_repository.py
src/infrastructure/providers/     rtd_profit*, rtd_config, mercado_data_provider, openfast_socket_adapter, mock_market_data, feriados_b3_provider, dividendos_statusinvest, calendario_resultados_*, mercado_estrutural_provider
src/infrastructure/notifications/ telegram_notifier.py, telegram_service.py
src/infrastructure/importers/     excel_importer.py
src/infrastructure/services/      som_service.py
src/ui/desktop/                   main_window, monitor_worker, column_utils, theme, 30+ dialogs/models
scripts/                          14 scripts: importflash, runtime_hook, monitorar_*, build_redistribuicao, …
config/                           parametros_default.json, spreadhunter_prioridade.json
```

**Arquitetura não-óbvia:**
- `monitor_worker.py` está em `src/ui/desktop/` (QThread que coordena use cases via sinais PySide6)
- Bootstrap: `src/infrastructure/persistence/bootstrap.py` → `main.py`
- `MonitorWorker` instancia use cases no `__init__`; cache de repositório protegido por `threading.Lock`
- `.env` contém credenciais opcoes.net.br — nunca commitar

## Regras de negócio inquebráveis

1. **Strike NUNCA persistido.** Vem só do RTD em tempo real. `InstrumentoOpcional.strike` é fallback opcional em memória. Se RTD não fornecer, **falhar ruidosamente**. NUNCA extrair strike do sufixo do código B3 (`G445` ≠ 44.50 após ajustes). Fontes confiáveis: RTD → `opt[3]` da API OptionsChain → fallback memória.

2. **MOD (`tipo_opcao`) só da CALL.** PUTs B3 são sempre Europeias (`E`), só CALLs podem ser Americanas (`A`). Em `importflash.py`, ler `r["mod"]` **apenas quando `r["tipo"] == "CALL"`**. PUT não sobrescreve.

3. **Parametrização obrigatória.** TODO valor de negócio (dias, %, limiares, timeouts, margens) vem do banco — nunca hardcoded. Fluxo: `database.py` (seed) → `parametro_operacional.py` (defaults) → `parametros_widget.py` (UI) → `regras_dialog.py` (exibição). Use cases/providers leem com `repo.get_by_chave()`. Exceções: constantes matemáticas (0.5, 100%), valores estruturais (2 pernas), cosmética (sons, timers UI). Ao adicionar parâmetro novo, tocar **todos**: seed `database.py`, `parametro_operacional.py`, `config/parametros_default.json`, `parametros_widget.py`.

4. **Custos B3** usam prêmio da opção / preço da ação como base (NUNCA strike). Ida-e-volta (×2). Collar inclui perna de ação. Em `calculadora_colar_calendario.py`, NÃO há `max(pnl - custo, 0.0)` — viabilidade usa PnL bruto.

5. **Chave composta `(ativo, cod_opcao)` é obrigatória.** Códigos B3 não são únicos entre ativos. Toda cache/mapa interno usa `f"{ativo}|{cod_put}"`. NUNCA use o 5º caractere do código como classe (A-L=CALL, M-Z=PUT; não há ON/PN no código).

6. **Coerência do book** — regra absoluta: **quem vende recebe `bid_*`, quem compra paga `ask_*`**. Nunca inverter. Comprar ativo: paga **ask** (`of_venda_ativo`). Vender ativo: recebe **bid** (`of_compra_ativo`). `of_venda_*` = ASK (você paga); `of_compra_*` = BID (você recebe). **Taxa**: `receb = bid_ativo − ask_call`. **BOX Vendida**: `receb = bid_ativo + bid_put − ask_call`. **SBTH Vendida**: `receb = bid_ativo + bid_put`; filtro `K > ativo × DIST`. **Collar**: `preco_compra_ativo` usa `of_venda_ativo` (ask).

7. **Box 4P** (`calculadora_box.py`, `lucro = clr - distancia`): **short box** — fórmula correta. Não inverter.

8. **Blacklist** (`black_list_import`): 53 ativos removidos do banco na importação, **sem preservação**. Importador único: `importflash.py` (⚡ Importar). Usa API `OptionsChain` para todas as séries (mensais + W1-W4).

## Operação B3

Mercado B3: seg-sex **10:00–17:00** (horário de Brasília). Fora disso o RTD do Profit não retorna dados → scans vazios. Testar com cotação dummy ou mock.

## Windows / PyInstaller — gotchas

- **DB path nunca hardcoded.** Use `get_db_path()` de `database.py` — banco fica em `%APPDATA%/Spreadhunter/spreadhunter.db`. Migração automática de `config/` legado via `_migrar_banco_legado()`. Em `importflash.py`, nunca `PROJECT_DIR / "config" / "spreadhunter.db"` — quebra no .exe.
- **Import roda em QThread**, não QProcess. `QProcess` com `sys.executable` não funciona no .exe (sem Python). Ver `_ImportThread` em `main_window.py`.
- **`hiddenimports` do `spreadhunter.spec` são obrigatórios.** Já mapeados (NÃO remover): `PIL`, `PIL._tkinter_finder`, `matplotlib.backends.backend_qtagg`, `scipy.stats`, `scipy.optimize`, `win32com`, `pythoncom`, `pywintypes`, `tzdata`. Sintoma de hidden import faltando: `ModuleNotFoundError` no .exe mas funciona no código-fonte. **PIL/Pillow não vai em `excludes`** (matplotlib `colors.py` depende dele).
- **COM thread safety**: RTD `refresh(timeout_ms)` roda síncrono na thread do worker — sem `CoInitialize` em thread separada → evita `RPC_E_WRONG_THREAD`. Timeout via parâmetro `rtd_refresh_timeout_ms` (seed 5000ms; 0 = sem limite).
- **`logger = logging.getLogger(__name__)`** no topo do arquivo. No PyInstaller pode ocorrer `name 'logger' is not defined` se `__name__` não bater com o módulo real. Se persistir, `logging.getLogger()` sem arg.

## UI / Qt — padrões consolidados

- **Segfault C++ ao arrastar coluna**: Qt conflita `sectionMoved` (drag) + `layoutChanged` (sort). **Sempre** usar `QTimer.singleShot(0, lambda: ...)` no handler de `sectionMoved`/`sectionResized`. Em `atualizar_resultados()`: `sectionsMovable(False)` + `blockSignals(True)` durante `beginResetModel()`/`endResetModel()`.
- **Persistência de colunas via QSettings** em `column_utils.py`. Testes em `tests/test_column_crash.py`.
- **Filtros auto-documentados**: ordem constante no próprio use case (`FILTROS_COLAR` em `monitor_colares.py`, etc.). `regras_dialog.py` importa dinamicamente. Para nova estratégia: crie constante e registre em `_FILTROS_POR_ESTRATEGIA`.
- **`ParametrosWidget`**: sidebar (QListWidget) + QStackedWidget. `bind_monitor_signals(worker)` liga sinais. QSettings persiste `parametros/last_section`.

## Pipeline (worker) — cuidados ao mexer

`monitor_worker.py` (QThread) tem estágios numerados. Estágio final chama `_processar_otimizado()` → `CalculadoraCaudaAssincrona.processar_otimizado()` → persiste na tabela `historico_simulacoes`.

**Onda 1 / `_flush_buffer` (crítico):** sempre que mexer em `_registrar_batch_inteligente()` ou `capturar_dados_mercado()`, verifique se **TODOS** os branches chamam `self._flush_buffer()` depois. Esquecer → opções nunca assinadas → book=0 mesmo com FAST conectado.

Book detection: scan **não** remove de `_chaves_com_book` se dado RTD não chegou. `recarregar_parametros()` limpa TODOS os caches → re-detecção completa. Manutenção a cada ~5s (%2), batch de 500.

## Performance intencional

Conexões SQLite abrindo/fechando, `O(n²)` em listas pequenas, `except Exception: pass` em não-críticos. PRAGMAs: `synchronous=NORMAL`, `cache_size=-8000`, `temp_store=MEMORY`, `journal_mode=WAL`. CAB skip se não mudou → reusa `_dados_cache`. MPP: `mpp_habilitado` no banco (default 0), instantâneo só após Onda 1.

## Convenções de código

Type hints obrigatórios em funções públicas. `snake_case` funções/variáveis, `PascalCase` classes. Imports: stdlib → third-party → local. `@dataclass` para DTOs/resultados. Repositórios: `get_by_chave()`, `save()`, `delete_all()`. Thread safety: `threading.Lock` em caches de repositório (SQLite via `threading.local` pool — key = `hashlib.md5(path)`). Diálogos: `setup_ui()`, `atualizar_resultados()`.

## Referências

- `.claude.md` — espelho subset deste arquivo
- `.opencode/skills/spreadhunter/SKILL.md` — skill carregável (mesmas regras)
- `INSTRUCOES_AMIGO.txt` — passo a passo para rodar via dev (diagnóstico quando .exe para)
- `docs/DISTRIBUICAO.md`, `docs/pnt_importacao.md` — deploy/PNT
- `graphify-out/` — knowledge graph; use a skill graphify em vez de grep crus
- `calendario_b3.py`: `np.busday_count` encapsulado em try/except para datas não-úteis — manter o try/except

## Observação técnica

`dc_to_du()` em `calendario_b3.py` já tem os dois modos: `dc_to_du_exato()` (com feriados) quando datas são fornecidas, e `dc_to_du_aproximado()` (252 dias) como fallback. Pendente: validar se o Profit Pro usa DC→DU exato ou aproximado para o `T` do Black-Scholes — se exato, migrar calculadoras de calls avulsas para `dc_to_du_exato(hoje, inst.vencimento)`.

## Recomendação de Modelos (ordem de uso preferida)

1. **DeepSeek (V3 ou R1)** — melhor escolha. Raciocínio matemático/financeiro nativo. Excelente aderência a arquiteturas complexas com regras de negócio cruzadas. Entende threading Python (QThread, locks) de forma confiável. DeepSeek-R1 raciocina antes de codar, evitando bugs em fórmulas críticas.
2. **Qwen 3 (Plus)** — segunda opção. Muito bom em Python com bibliotecas científicas (scipy, numpy, matplotlib). Tende a respeitar type hints e convenções.
3. **GLM-Z1 / GLM 5-2** — funcional mas perde precisão em código financeiro quantitativo. Pode confundir Clean Architecture. Melhor para tarefas UI simples.

**Refatoração crítica** (mexer com cuidado): `monitor_worker.py`, `monitor_colares_calendario.py`, `calculadora_*.py`, `calculadora_cauda_assincrona.py`, `database.py`, `repositories.py`, `parametro_operacional.py`, `main_window.py`.

**Rotineiro** (sem impacto em cálculo/dados): tests, dialogs, models de tabela, tooltips, parâmetros, colours, `column_utils.py`, `regras_dialog.py`, filtros, labels.
