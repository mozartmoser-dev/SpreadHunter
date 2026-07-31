# Spreadhunter — Regras para Agentes

Varredura de oportunidades em opções B3 (colar, collar calendário, box, MPP, taxa, SBTH vendida, put ratio, venda coberta). Desktop Python/PySide6, SQLite, RTD via COM do Profit, socket OpenFast, API opcoes.net.br. **Windows-only.** Sem CI; 573 testes rodam localmente.

## Confirmação obrigatória

**NUNCA aplique alterações sem antes apresentar a proposta e obter confirmação explícita** (use `question`). Fluxo: proposta → confirmação → execução.

## Comandos essenciais

```powershell
python -m pytest tests/ -x -q --tb=short            # todos (573)
python -m pytest tests/domain/test_calculadora_cauda_assincrona.py -q
python -m pytest tests/test_fase3.py::TestX::test_y -q
python main.py                                       # dev
python -m pip install -r requirements.txt            # instalar dependências
python -m PyInstaller --clean --distpath "$env:USERPROFILE\Desktop\dist" `
  --workpath "$env:USERPROFILE\Desktop\build_pyi" spreadhunter.spec
```

Stack: Python ≥3.13, PySide6 6.11.1, sqlite3, scipy, numpy, matplotlib, pywin32, pillow, opencv-python, requests, python-dotenv, pyautogui, psutil, pytest, yfinance. `pyproject.toml` seta `pythonpath = ["."]` (imports from root). `requirements.txt` pinado. Regras completas em `.opencode/skills/spreadhunter/SKILL.md` (`skill spreadhunter`).

## Arquitetura não-óbvia

- `monitor_worker.py` em `src/ui/desktop/` (QThread que coordena 7+ use cases via sinais)
- Pipeline real no worker: 1. Geral → 2. Colares → 3. Collar Calendário → 4. Box 4P → 5. Put Ratio → 6. Manutenção → 7. Reconexão → 8. MPP. Onda 2 roda dentro da Manutenção.
- Use cases em `src/application/use_cases/`, calculadoras em `src/domain/services/`
- Bootstrap: `src/infrastructure/persistence/bootstrap.py` → `main.py`
- `_ImportThread` em `grade_opcoes_dialog.py` (não em `main_window.py`)
- Duas fontes de market data: Profit RTD (COM, `rtd_profit.py`) e OpenFast (socket TCP, `openfast_socket_adapter.py`). Config `fonte_market_data` no banco. **Atenção:** `parametro_operacional.py` default hardcoded = `"profit"`, mas `parametros_default.json` seed = `"openfast"` — o JSON vence no seed. Script `scripts/set_openfast.py` alterna.
- `.env` contém credenciais opcoes.net.br — `.gitignore` exclui, nunca commitar. `load_dotenv()` é chamado em `opcoesnet_client.py` (linha ~11, no import do módulo), não globalmente.
- DB em `%APPDATA%/Spreadhunter/spreadhunter.db` via `get_db_path()` — nunca hardcoded. Migração automática de `config/spreadhunter.db` na 1ª execução.
- Conexão SQLite: `threading.local` pool, `journal_mode=WAL`, `cache_size=-8000`, `temp_store=MEMORY`, `synchronous=NORMAL`
- `config/spreadhunter_prioridade.json` — prioridades de ativos
- Graphify: `graphify-out/` — use `skill graphify` para consultas de arquitetura. Para perguntas focadas, prefira graphify query (subgrafo escopado) ao invés de grep nos arquivos fonte. Leia `GRAPH_REPORT.md` apenas para contexto arquitetural amplo.

## Regras de negócio (resumo; detalhes em SKILL.md)

1. **Strike NUNCA persistido.** Vem do RTD em tempo real. Se RTD não fornecer, falhar. NUNCA extrair do sufixo B3 (`G445` ≠ 44.50).
2. **MOD (`tipo_opcao`) só da CALL.** PUTs B3 são Europeias (`E`). Ler `r["mod"]` apenas quando `r["tipo"] == "CALL"`. O scanner Box 4P rejeita pares onde a CALL K1 não é Europeia se `box_soh_europeia=1` (default, `monitor_box.py:178`). `box_soh_europeia=0` aceita CALL Americanas (PUT sempre E).
3. **Parametrização obrigatória do banco.** TODO valor de negócio via `repo.get_by_chave()`. Nunca hardcoded. Ao adicionar parâmetro, tocar: `config/parametros_default.json` (seed) + `parametro_operacional.py` (fallback) + `parametros_widget.py` + `regras_dialog.py`.
4. **Custos B3** usam prêmio/preço (NUNCA strike). Ida-e-volta (×2).
5. **Chave composta `(ativo, cod_opcao)`.** Toda cache/mapa usa `f"{ativo}|{cod}"`.
6. **Coerência do book:** `of_venda_*` = ASK (você paga); `of_compra_*` = BID (você recebe). Comprar ativo: paga `of_venda_ativo`. **Taxa**: `receb = bid_ativo − ask_call`. **BOX Vendida**: `receb = bid_ativo + bid_put − ask_call`. **SBTH Vendida**: `receb = bid_ativo + bid_put`.
7. **Box 4P** (`calculadora_box.py`): `lucro = clr - distancia` — short box, não inverter.
8. **Blacklist** (`black_list_import`): ativos removidos na importação, sem preservação.
9. **Importador único:** `scripts/validar_opcoes/importflash.py`. API `OptionsChain` para todas as séries (mensais + W1-W4).

## Operação B3

Mercado: seg-sex **10:00–17:00** (Brasília). Fora disso RTD/OpenFast não retornam dados. Testar com cotação dummy ou mock (`mock_market_data.py`).

## Windows / PyInstaller gotchas

- **Import em QThread** (`grade_opcoes_dialog.py:_ImportThread`), não QProcess — `sys.executable` falha no .exe.
- **`hiddenimports` do `spreadhunter.spec` obrigatórios.** Já mapeados. Sintoma de falta: `ModuleNotFoundError` no .exe mas funciona no fonte.
- **COM thread safety**: `CoInitializeEx(COINIT_APARTMENTTHREADED)` no início de `MonitorWorker.run()`. `refresh(timeout_ms)` síncrono na thread do worker.
- **`runtime_hook.py`** em `scripts/` seta `MPLBACKEND` e adiciona `pywin32_system32` ao PATH do DLL.

## UI / Qt

- **Segfault ao arrastar coluna:** Qt conflita `sectionMoved` (drag) + `layoutChanged` (sort). Sempre usar `QTimer.singleShot(0, lambda: ...)` no handler. **Não mexer** em `main_window.py:364` e `mpp_dialog.py:94` sem resolver.
- Em `atualizar_resultados()`: `sectionsMovable(False)` + `blockSignals(True)` durante `beginResetModel()`/`endResetModel()`.
- **Persistência de colunas** via QSettings em `column_utils.py`.
- **Filtros auto-documentados** nos use cases (`FILTROS_COLAR`, `FILTROS_COLLAR_CALENDARIO`). `regras_dialog.py` importa dinamicamente via `_FILTROS_POR_ESTRATEGIA`.

## `_flush_buffer` (crítico)

Em `mercado_data_provider.py` — sempre que mexer em `_registrar_batch_inteligente()` ou `capturar_dados_mercado()`, TODOS os branches devem chamar `self._flush_buffer()`. Esquecer → opções nunca assinadas → book=0 mesmo com FAST conectado.

## Refatoração: crítico vs. rotineiro

**Crítico** (cálculo/dados): `monitor_worker.py`, `monitor_colares_calendario.py`, `calculadora_*.py`, `calculadora_cauda_assincrona.py`, `database.py`, `repositories.py`, `parametro_operacional.py`, `main_window.py`.

**Rotineiro** (UI/tooltips/parâmetros): tests, dialogs, models de tabela, `column_utils.py`, `regras_dialog.py`, filtros, cores, labels.

## Referências

- `.opencode/skills/spreadhunter/SKILL.md` — use `skill spreadhunter` para regras completas + histórico de sessões
- `.claude.md` — resumo adicional de stack e convenções
- `docs/DISTRIBUICAO.md`, `docs/pnt_importacao.md` — deploy/PNT
- `pendenciascalendario.md` — diagnóstico BWB + simulações
- `planoprotecaocauda.md` — planejamento de proteção de cauda
- `INSTRUCOES_AMIGO.txt` — diagnóstico .exe
