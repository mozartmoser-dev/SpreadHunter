# Spreadhunter — Regras para Agentes

Sistema de varredura de oportunidades em opções B3 (colar, collar calendário, box,
MPP, taxa, SBTH vendida). Desktop Python/PySide6, SQLite, RTD via COM do Profit,
API opcoes.net.br. **Windows-only.** Sem CI; testes rodam localmente.

## Confirmação obrigatória

**NUNCA aplique alterações sem antes apresentar a proposta e obter confirmação
explícita** (use `question`). Fluxo: proposta → confirmação → execução.

## Comandos essenciais

```powershell
# Testes (sempre rodar antes de buildar)
python -m pytest tests/ -x -q --tb=short
python -m pytest tests/test_calculadora_cauda_assincrona.py -q   # um arquivo
python -m pytest tests/test_fase3.py::TestX::test_y -q           # um teste

# Rodar app (desenvolvimento)
python main.py

# Buildar .exe (deploy sempre para C:\Users\Mozart\Desktop\Spreadhunter\)
python -m PyInstaller --clean --distpath "$env:USERPROFILE\Desktop\dist" `
  --workpath "$env:USERPROFILE\Desktop\build_pyi" spreadhunter.spec
```

Stack: Python 3.13.14 (`C:\Program Files\Python313\python.exe`), PySide6 6.11.1,
sqlite3 (stdlib), scipy 1.17.1, numpy 2.4.6, matplotlib 3.11.0, pywin32 312,
pytest 9.1.0. **430 testes**. Resto em `requirements.txt` (pinado).

## Estrutura — onde mora o que

```
src/application/use_cases/   monitor_*.py, mpp_use_case.py, exportar_operacao.py
src/domain/entities/         entidades (InstrumentoOpcional, ParametroOperacional...)
src/domain/services/         calculadora_cauda_assincrona.py, pipeline_tracker.py
src/infrastructure/integrations/   opcoesnet_client.py (API B3)
src/infrastructure/persistence/    database.py (SQLite + PRAGMAs + seed params)
src/infrastructure/persistence/repositories/  repositories.py (todos os repos)
src/infrastructure/providers/      rtd_profit.py, mercado_data_provider.py, openfast_socket_adapter.py
src/ui/desktop/                    main_window.py, monitor_worker.py, dialogs, models
scripts/validar_opcoes/importflash.py  — único importador (⚡ Importar)
config/parametros_default.json         — defaults de parâmetros (fonte)
```

**Arquitetura não-óbvia:**
- `monitor_worker.py` está em `src/ui/desktop/`, **não** em `src/application/use_cases/`.
  É um `QThread` que coordena todos os use cases via sinais PySide6 e dispara
  estágios (capturar → cauda assíncrona → otimizado → persistir).
- Bootstrap: `src/infrastructure/persistence/bootstrap.py` → `main.py`.
- O `MonitorWorker` instancia use cases no `__init__` (db_path passado por toda
  a cadeia). Cache de repositório protegido por `threading.Lock`.

## Regras de negócio inquebráveis

1. **Strike NUNCA persistido.** Vem só do RTD em tempo real.
   `InstrumentoOpcional.strike` é fallback opcional em memória. Se RTD não
   fornecer, **falhar ruidosamente** — não adivinhar, não usar banco.
   Também **NUNCA extrair strike do sufixo do código B3** (`G445` ≠ 44.50 após
   ajustes). Fontes confiáveis: RTD → `opt[3]` da API OptionsChain → fallback memória.

2. **MOD (`tipo_opcao`) só da CALL.** PUTs B3 são sempre Europeias (`E`), só
   CALLs podem ser Americanas (`A`). Em `importflash.py`, ler `r["mod"]`
   **apenas quando `r["tipo"] == "CALL"`**. PUT não sobrescreve.

3. **Parametrização obrigatória.** TODO valor de negócio (dias, %, limiares,
   timeouts, margens) vem do banco — nunca hardcoded. Fluxo:
   `database.py` (seed) → `parametro_operacional.py` (defaults)
   → `parametros_widget.py` (UI) → `regras_dialog.py` (exibição).
   Use cases/providers leem com `repo.get_by_chave()`.
   Exceções: constantes matemáticas (0.5, 100%), valores estruturais (2 pernas),
   cosmética (sons, timers UI).

   Ao adicionar parâmetro novo, tocar **todos** os pontos: seed `database.py`,
   `parametro_operacional.py`, `config/parametros_default.json`,
   `parametros_widget.py`. Faltar um = UI quebra ou default divergente.

4. **Custos B3** usam prêmio da opção / preço da ação como base (NUNCA strike).
   Ida-e-volta (×2). Collar inclui perna de ação. Em `calculadora_colar_calendario.py`,
   NÃO há `max(pnl - custo, 0.0)` — viabilidade usa PnL bruto.

5. **Chave composta `(ativo, cod_opcao)` é obrigatória.** Códigos B3 não são
   únicos entre ativos (PETR3 e PETR4 podem ter mesmo código em séries
   distintas). Toda cache/mapa interno usa `f"{ativo}|{cod_put}"`.
   `_chaves_registradas`, `_chaves_com_book`, `_chaves_detalhes_completos`,
   `_dados_cache`, `_cab_anterior`, `dados_mercado` (output), `inst_map`
   (`get_all_mapped()`) — todos compostos. **NUNCA** use o 5º caractere do
   código como classe (A-L=CALL, M-Z=PUT; não há ON/PN no código).

6. **Coerência do book** — regra absoluta: **quem vende recebe `bid_*`,
   quem compra paga `ask_*`**. Nunca inverter. Aplica-se a TODO cálculo
   de custo/recebimento/prêmio, em qualquer estratégia:
   - Comprar ativo: paga **ask** (`of_venda_ativo`), NUNCA bid.
   - Vender ativo: recebe **bid** (`of_compra_ativo`), NUNCA ask.
   - Comprar opção: paga **ask** (`of_venda_*`).
   - Vender opção: recebe **bid** (`of_compra_*`).
   - **Atenção aos nomes:** `of_venda_*` = oferta de venda no book = ASK
     (você paga); `of_compra_*` = oferta de compra no book = BID (você
     recebe). Referem-se ao **lado do book**, não ao lado do trader.
   - **Taxa** (renomeada de Venda Coberta): `receb = bid_ativo − ask_call`
   - **BOX Vendida**: `receb = bid_ativo + bid_put − ask_call`
   - **SBTH Vendida**: `receb = bid_ativo + bid_put`; filtro `K > ativo × DIST`
   - **Collar (protetivo e calendário)**: `preco_compra_ativo` usa
     `of_venda_ativo` (ask), que é o que se paga ao comprar a ação.
     Bug histórico: inverter bid/ask ao calcular capital empregado
     → subestima capital → infla % CDI artificialmente.

7. **Box 4P** (`calculadora_box.py`, fórmula `lucro = clr - distancia`): é
   **short box** — fórmula correta. Não inverter.

8. **Blacklist** (`black_list_import`): 53 ativos removidos do banco na
   importação, **sem preservação**. Importador é só `importflash.py` (⚡ Importar).
   Usa API `OptionsChain` para todas as séries (mensais + W1-W4).

## Operação B3

Mercado B3: seg-sex **10:00–17:00** (horário de Brasília). Fora disso o RTD
do Profit não retorna dados → scans vazios. Banco de horário real: rodar
testes com cotação dummy ou mock.

## Windows / PyInstaller — gotchas

- **DB path nunca hardcoded.** Use `get_db_path()` de `database.py` — banco
  fica em `%APPDATA%/Spreadhunter/spreadhunter.db` (persistent across updates).
  Migração automática de `config/` legado via `_migrar_banco_legado()`.
  Em `importflash.py`, **nunca** `PROJECT_DIR / "config" / "spreadhunter.db"`
  — quebra no .exe (PyInstaller resolve `__file__` para temp dir).

- **Import roda em QThread**, não QProcess. `QProcess` com `sys.executable`
  não funciona no .exe (sem Python). Ver `_ImportThread` em `main_window.py`.

- **`hiddenimports` do `spreadhunter.spec` são obrigatórios.** Sempre que
  adicionar lib nova, ver se precisa incluir. Já mapeados (NÃO remover):
  `PIL`, `PIL._tkinter_finder`, `matplotlib.backends.backend_qtagg`,
  `scipy.stats`, `scipy.optimize`, `win32com`, `pythoncom`, `pywintypes`,
  `tzdata`. Sintoma de hidden import faltando: `ModuleNotFoundError` no .exe
  mas funciona no código-fonte. **PIL/Pillow não vai em `excludes`** (matplotlib
  `colors.py` depende dele).

- **COM thread safety**: RTD `refresh(timeout_ms)` roda síncrono na thread
  do worker — sem `CoInitialize` em thread separada → evita
  `RPC_E_WRONG_THREAD`. Timeout via parâmetro `rtd_refresh_timeout_ms`
  (seed 5000ms; 0 = sem limite).

- **`logger = logging.getLogger(__name__)` no topo do arquivo.** No
  PyInstaller pode ocorrer `name 'logger' is not defined` se `__name__`
  não bater com o módulo real. Se persistir, `logging.getLogger()` sem arg.

## UI / Qt — padrões consolidados

- **Segfault C++ ao arrastar coluna**: Qt conflita `sectionMoved` (drag) +
  `layoutChanged` (sort). **Sempre** usar `QTimer.singleShot(0, lambda: ...)`
  no handler de `sectionMoved`/`sectionResized` — posterga para próximo
  ciclo do event loop após sort/drag finalizarem. Padrão em todos os dialogs:
  ```
  header.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header, KEY)))
  header.sectionResized.connect(lambda: QTimer.singleShot(0, lambda: salvar_largura_colunas(header, KEY_W)))
  limpar_e_restaurar_colunas(header, KEY_ORDER, KEY_W)  # restaura com limpeza de lixo órfão
  ```
  Em `atualizar_resultados()`: `sectionsMovable(False)` + `blockSignals(True)`
  durante `beginResetModel()`/`endResetModel()`.

- **Persistência de colunas via QSettings** em `column_utils.py`:
  `salvar_ordem_colunas`, `restaurar_ordem_colunas`, `salvar_largura_colunas`,
  `restaurar_largura_colunas`, `limpar_e_restaurar_colunas`. A "limpeza
  automática" descarta snapshots com nº de colunas divergente do header
  atual (evita lixo órfão). Testes em `tests/test_column_crash.py`.

- **Filtros auto-documentados**: a ordem dos filtros é constante no próprio
  use case (`FILTROS_COLAR` em `monitor_colares.py:18`,
  `FILTROS_COLLAR_CALENDARIO` em `monitor_colares_calendario.py:25`).
  `regras_dialog.py` importa dinamicamente e exibe. Para nova estratégia:
  crie a constante e registre em `_FILTROS_POR_ESTRATEGIA` no `regras_dialog.py`.

- **`ParametrosWidget`** é sidebar (QListWidget) + QStackedWidget; cada
  estratégia é uma página. `bind_monitor_signals(worker)` liga sinais do
  `MonitorWorker` aos contadores reativos. QSettings persiste
  `parametros/last_section`.

## Pipeline (worker) — cuidados ao mexer

`monitor_worker.py` (QThread) tem estágios numerados. Estágio final chama
`_processar_otimizado()` → `CalculadoraCaudaAssincrona.processar_otimizado()`
(estático) → persiste lote na tabela `historico_simulacoes` via
`HistoricoSimulacoesRepository`.

**Onda 1 / `_flush_buffer` (crítico):** sempre que mexer em
`_registrar_batch_inteligente()` ou `capturar_dados_mercado()`, verifique
se **TODOS** os branches chamam `self._flush_buffer()` depois. O retorno é
a lista de inscrições que precisa ir ao socket. Esquecer → opções nunca
assinadas → book=0 mesmo com FAST conectado. Bug histórico foi adicionado
só em ativos prioritários e esquecido na Onda 1 geral.

Book detection: scan **não** remove de `_chaves_com_book` se dado RTD não
chegou. `recarregar_parametros()` limpa TODOS os caches → re-detecção
completa. Manutenção a cada ~5s (%2), batch de 500.

## Performance intencional — não "corrigir" sem confirmar

Várias escolhas são deliberadas: conexões SQLite abrindo/fechando, `O(n²)` em
listas pequenas, `except Exception: pass` em não-críticos. PRAGMAs SQLite:
`synchronous=NORMAL`, `cache_size=-8000`, `temp_store=MEMORY`, `journal_mode=WAL`.
CAB skip se não mudou → reusa `_dados_cache`. MPP: `mpp_habilitado` no banco
(default 0), instantâneo só após Onda 1.

## Convenções de código

- Type hints obrigatórios em funções públicas
- `snake_case` funções/variáveis, `PascalCase` classes
- Imports: stdlib → third-party → local (separados por linha em branco)
- `@dataclass` para DTOs/resultados
- Repositórios: `get_by_chave()`, `save()`, `delete_all()`
- Thread safety: `threading.Lock` em caches de repositório (SQLite via
  `threading.local` pool — key = `hashlib.md5(path)` porque path Windows tem
  `\` e `:` quebram `AttributeError`)
- Diálogos: `setup_ui()`, `atualizar_resultados()`

## Histórico/arquivos auxiliares

- `.claude.md` — regras críticas abreviadas (espelho subset deste arquivo)
- `.opencode/skills/spreadhunter/SKILL.md` — skill carregável (mesmas regras)
- `INSTRUCOES_AMIGO.txt` — passo a passo para rodar via dev (diagnóstico
  quando .exe para de funcionar: rodar `python main.py` e ver stacktrace)
- `docs/DISTRIBUICAO.md`, `docs/pnt_importacao.md` — específicos de deploy/PNT
- `graphify-out/` — knowledge graph do repo; para perguntas focadas use
  a skill graphify (scoped subgraph) em vez de grep crus
- `calendario_b3.py`: `np.busday_count` encapsulado em try/except para
  datas não-úteis (crash fim de semana) — manter o try/except

## Pendência aberta

Validar se o Profit Pro usa **DC→DU exato (com feriados)** ou
**aproximado (252/365)** para o `T` no Black-Scholes. Se exato, migrar
calculadoras para `dc_to_du_exato(hoje, inst.vencimento)` em vez de
`dc_to_du(None, None, dias)`. Teste: comparar IV do Profit vs IV próprio
com `T_exato` vs `T_aproximado` para um papel de vencimento conhecido.

## Recomendação de Modelos (opencode Go)

Quando eu sugerir qual modelo usar, sigo a classificação abaixo:

1. 🥇 **DeepSeek (V3 ou R1)** — melhor escolha para este sistema.
   - Raciocínio matemático/financeiro nativo (Black-Scholes, otimizações
     numéricas).
   - Excelente aderência a arquiteturas complexas com muitas regras de
     negócio cruzadas.
   - Entende threading Python (QThread, locks, thread safety) de forma
     confiável.
   - Segue regras de AGENTS.md com alta fidelidade — não "inventa" atalhos.
   - DeepSeek-R1 raciocina antes de codar, evitando bugs em fórmulas
     financeiras críticas.

2. 🥈 **Qwen 3 (Plus)** — segunda opção sólida, especialmente com modo
   thinking ativado.
   - Muito bom em Python com bibliotecas científicas (scipy, numpy,
     matplotlib).
   - Qwen3-235B (API Plus) tem benchmark de código comparável ao
     DeepSeek-V3.
   - Tende a respeitar type hints e convenções — importante para o padrão
     do Spreadhunter.
   - Limitação: às vezes "criativo demais" com arquitetura quando não há
     contexto suficiente.

3. 🥉 **GLM-Z1 / GLM 5-2** — funcional mas com ressalvas importantes.
   - Bom em Python genérico, mas perde precisão em código financeiro
     quantitativo.
   - Pode confundir a separação domain/application/infrastructure (Clean
     Architecture).
   - Histórico de erros em fórmulas Black-Scholes e cálculos de gregas.
   - Melhor para tarefas UI simples do que para calculadoras de opções.

**Ordem de uso preferida pelo usuário:** DeepSeek → Qwen 3 → GLM.

⚠️ **Refatoração crítica** = mexer em:
- `monitor_worker.py`, `monitor_colares_calendario.py`
- `calculadora_*.py`, `calculadora_cauda_assincrona.py`
- `database.py`, `repositories.py` (schema, migrações)
- `parametro_operacional.py`, `main_window.py` (lógica estrutural)

✅ **Rotineiro** = ajustes em:
- Tests, dialogs, models de tabela, tooltips, parâmetros, colours
- `column_utils.py`, `regras_dialog.py`, filtros, labels
- Pequenos fixes sem impacto no cálculo ou nos dados
