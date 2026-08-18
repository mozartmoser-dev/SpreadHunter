# Spreadhunter — Regras para Agentes

Varredura de oportunidades em opções B3 (colar, collar calendário, box, MPP, taxa, SBTH vendida, put ratio, venda coberta). Desktop Python/PySide6, SQLite, RTD via COM do Profit, socket OpenFast, API opcoes.net.br. **Windows-only.** Sem CI (sem `.github/`); ~797 testes coletados localmente (contagem muda com frequência; validar com `--collect-only`).

## Confirmação obrigatória

**NUNCA aplique alterações sem antes apresentar a proposta e obter confirmação explícita** (use `question`). Fluxo: proposta → confirmação → execução.

## Comandos essenciais

```powershell
python -m pytest tests/ -x -q --tb=short            # todos (797 coletados; --collect-only ~15-25s)
python -m pytest tests/domain/test_calculadora_cauda_assincrona.py -q
python -m pytest tests/test_fase3.py::TestX::test_y -q
python main.py                                       # dev
python -m pip install -r requirements.txt            # instalar dependências
python -m PyInstaller --clean --distpath "$env:USERPROFILE\Desktop\dist" `
  --workpath "$env:USERPROFILE\Desktop\build_pyi" spreadhunter.spec
```

Stack: Python 3.13 local (pyproject permite ≥3.12), PySide6 6.11.1, sqlite3, scipy, numpy, matplotlib, pywin32, requests, yfinance. `pyproject.toml` seta `pythonpath = ["."]` (imports from root). `requirements.txt` pinado. **Sem lint/typecheck/formatter configurado — validação é via pytest.**

## Arquitetura não-óbvia

- `monitor_worker.py` em `src/ui/desktop/` (QThread que coordena 7+ use cases via sinais)
- Pipeline real no worker: 0. Manutenção (promove novas chaves) → 1. Geral → 2. Colares → 3. Collar Calendário → 4. Box 4P → 5. Put Ratio → 6. Reconexão → 7. MPP. Onda 2 roda dentro da Manutenção.
- Use cases em `src/application/use_cases/`, calculadoras em `src/domain/services/`
- Bootstrap: `src/infrastructure/persistence/bootstrap.py` → `main.py`
- `_ImportThread` em `grade_opcoes_dialog.py` (não em `main_window.py`)
- Duas fontes de market data: Profit RTD (COM, `rtd_profit.py`) e OpenFast (socket TCP, `openfast_socket_adapter.py`), além de `fasttrade` (RTD da Fast Trade) e `mock` (simulador p/ testes) em `criar_data_source()` (`src/domain/services/market_data_source.py`). Config `fonte_market_data` no banco. **Atenção:** `src/domain/entities/parametro_operacional.py` default hardcoded = `"profit"`, mas `parametros_default.json` seed = `"openfast"` — o JSON vence no seed. Script `scripts/set_openfast.py` alterna.
- `.env` contém credenciais opcoes.net.br (`OPCOESNET_CPF`, `OPCOESNET_SENHA`) — `.gitignore` exclui, nunca commitar. `load_dotenv()` é chamado em `src/infrastructure/integrations/opcoesnet_client.py` (linha 19, no topo do módulo), não globalmente.
- DB em `%APPDATA%/Spreadhunter/spreadhunter.db` via `get_db_path()` — nunca hardcoded. Migração automática de `config/spreadhunter.db` na 1ª execução.
- Conexão SQLite: `threading.local` pool, `journal_mode=WAL`, `cache_size=-8000`, `temp_store=MEMORY`, `synchronous=NORMAL`
- `config/spreadhunter_prioridade.json` — prioridades de ativos
- Graphify: `graphify-out/` — índice estrutural/semântico auxiliar para reduzir exploração desnecessária do código e economizar contexto/tokens. Use `skill graphify` para consultas. Para perguntas focadas, prefira graphify query (subgrafo escopado) ao invés de grep nos arquivos fonte. Leia `graphify-out/GRAPH_REPORT.md` apenas para contexto arquitetural amplo.
  - **Atualização:** executar `graphify update .` ao final de uma sessão/etapa que produziu alterações relevantes em `src/**/*.py` ou `specs/**/*.md`. Usa cache incremental (sem custo de API). NÃO executar a cada comando ou em sessões sem mudanças estruturais.
  - **NÃO disparam atualização:** logs/, arquivos temporários, caches de runtime, traces, alterações triviais sem impacto estrutural.
  - **O plugin `graphify.js` apenas lê o grafo, não gera/atualiza.**

## Regras de negócio (resumo; detalhes em SKILL.md)

1. **Strike NUNCA persistido.** Vem do RTD em tempo real. Se RTD não fornecer, falhar. NUNCA extrair do sufixo B3 (`G445` ≠ 44.50).
2. **MOD (`tipo_opcao`) só da CALL.** PUTs B3 são Europeias (`E`). Ler `r["mod"]` apenas quando `r["tipo"] == "CALL"`. O scanner Box 4P rejeita pares onde a CALL K1 não é Europeia se `box_soh_europeia=1` (default, `src/application/use_cases/monitor_box.py:52`; default 1.0 em `parametro_operacional.py`). `box_soh_europeia=0` aceita CALL Americanas (PUT sempre E).
3. **Parametrização obrigatória do banco.** TODO valor de negócio via `repo.get_by_chave()`. Nunca hardcoded. Ao adicionar parâmetro, tocar: `config/parametros_default.json` (seed) + `parametro_operacional.py` (fallback) + `parametros_widget.py` + `regras_dialog.py`.
4. **Custos B3** usam prêmio/preço (NUNCA strike). Ida-e-volta (×2).
5. **Chave composta `(ativo, cod_opcao)`.** Toda cache/mapa usa `f"{ativo}|{cod}"`.
6. **Coerência do book:** `of_venda_*` = ASK (você paga); `of_compra_*` = BID (você recebe). Comprar ativo: paga `of_venda_ativo`. **Taxa**: `receb = bid_ativo − ask_call`. **BOX Vendida**: `receb = bid_ativo + bid_put − ask_call`. **SBTH Vendida**: `receb = bid_ativo + bid_put`.
7. **Box 4P** (`calculadora_box.py`): `lucro = clr - distancia` — short box, não inverter.
8. **Blacklist** (`black_list_import`): ativos removidos na importação, sem preservação.
9. **Importador único:** `scripts/validar_opcoes/importflash.py`. API `OptionsChain` para todas as séries (mensais + W1-W4).
10. **Semanais fora da Onda 1 por default:** `perf_filtro_semanal=1` (seed) exclui opções semanais (W em `cod[-2]`) do registro/varredura da Onda 1 em `mercado_data_provider.py` e `monitor_put_ratio.py`. Não é bug: instrumento semanal simplesmente não é assinado.

## Investigação de dados: protocolo obrigatório dos 7 elos

Antes de concluir que um campo está **ausente, atrasado, zerado ou divergente**, obrigatoriamente verificar a cadeia completa:

1. onde o campo é consumido;
2. onde deveria ser assinado no OpenFast;
3. se o tópico `(instrumento, campo)` está efetivamente registrado;
4. se o servidor entrega o campo quando assinado;
5. se o adapter recebe e armazena;
6. se o provider repassa o valor correto;
7. se o consumidor recebe e utiliza o mesmo valor.

Criar evidência/teste para cada elo relevante antes de propor uma correção.

**Não assumir que ausência de dado significa delay, divergência do feed ou erro de cálculo sem antes verificar a assinatura e a entrega real do campo.**

## Operação B3

Mercado: seg-sex **10:00–17:00** (Brasília). Fora disso RTD/OpenFast não retornam dados. Testar com cotação dummy ou `src/infrastructure/providers/mock_market_data.py`.

**Logging:** nível por parâmetro `diagnostico_logging` (0=off, default). Overrides env em `main.py`: `SH_LOG_LEVEL=DEBUG|INFO|...` e `SH_PROFILE_MERCADO=1` (gera `logs/profile_mercado.log` sobrescrito a cada execução, filtrado p/ Manutenção/Onda 1/_flush_buffer). Sem o override/param, market data não loga debug.

## Windows / PyInstaller gotchas

- **Import em QThread** (`grade_opcoes_dialog.py:_ImportThread`), não QProcess — `sys.executable` falha no .exe.
- **`hiddenimports` do `spreadhunter.spec` obrigatórios.** Já mapeados. Sintoma de falta: `ModuleNotFoundError` no .exe mas funciona no fonte.
- **COM thread safety**: `CoInitializeEx(COINIT_APARTMENTTHREADED)` no início de `MonitorWorker.run()`. `refresh(timeout_ms)` síncrono na thread do worker.
- **`runtime_hook.py`** em `scripts/` seta `MPLBACKEND` e adiciona `pywin32_system32` ao PATH do DLL.

## UI / Qt

- **Segfault ao arrastar coluna:** Qt conflita `sectionMoved` (drag) + `layoutChanged` (sort). Sempre usar `QTimer.singleShot(0, lambda: ...)` no handler. **Não mexer** nos `sectionMoved` handlers em `main_window.py` e `mpp_dialog.py` sem resolver.
- Em `atualizar_resultados()`: `sectionsMovable(False)` + `blockSignals(True)` durante `beginResetModel()`/`endResetModel()`.
- **Persistência de colunas** via QSettings em `column_utils.py`.
- **Filtros auto-documentados** nos use cases (`FILTROS_COLAR`, `FILTROS_COLLAR_CALENDARIO`). `regras_dialog.py` importa dinamicamente via `_FILTROS_POR_ESTRATEGIA`.

## Testes: gotchas

- **Crash nativo Qt conhecido:** `tests/test_fase4.py::TestMonitorTableModel::test_tipo_opcao_display` derruba o processo pytest (exit `0xC0000409`, heap corruption) de forma intermitente — pré-existente, não é regressão do seu patch. Se a suíte completa abortar com crash nativo, é este teste. Documentado também em `SKILL.md` (historico de sessoes).

## `_flush_buffer` (crítico)

Em `mercado_data_provider.py` — sempre que mexer em `_registrar_batch_inteligente()` ou `capturar_dados_mercado()`, TODOS os branches devem chamar `self._flush_buffer()`. Esquecer → opções nunca assinadas → book=0 mesmo com FAST conectado.

## Refatoração: crítico vs. rotineiro

**Crítico** (cálculo/dados): `monitor_worker.py`, `monitor_colares_calendario.py`, `calculadora_*.py`, `calculadora_cauda_assincrona.py`, `database.py`, `repositories.py`, `parametro_operacional.py`, `main_window.py`.

**Rotineiro** (UI/tooltips/parâmetros): tests, dialogs, models de tabela, `column_utils.py`, `regras_dialog.py`, filtros, cores, labels.

## Protocolo de alterações e validação

Fluxo para mudanças relevantes (cálculos, market data, timing, classificação, persistência, concorrência, fontes, pipelines):

1. **Proposta:** identificar problema/objetivo, arquivos afetados, regras que não devem mudar. Apresentar antes de implementar (regra de confirmação obrigatória).
2. **Implementação mínima:** só o necessário. Sem refatorações oportunistas, sem misturar melhorias independentes.
3. **Testes:** executar os relevantes (suíte completa quando apropriado). Resultados reais, não "parece correto".
4. **Evidência,** quando o risco justificar:
   - Performance → baseline antes/depois, escala representativa.
   - Cálculo → comparação/equivalência com implementação anterior confiável, harness ou dados frozen.
   - Nunca assumir que vetorização/refatoração é otimização sem medir.
5. **Revisão:** separar bug real, falso positivo, mudança deliberada e melhoria futura. Não tratar divergência como bug sem evidência.
6. **Commit:** só após validação. Apenas alterações intencionais, sem logs/traces/temporários.
7. **Push:** após commit validado, manter `main` sincronizada com `origin/main`.

**Validação proporcional ao risco:**
- Cosmético/documental → revisão simples.
- Lógica isolada → testes relevantes.
- Cálculo/regra de negócio → testes + comparação.
- Performance → baseline + benchmark.
- Market data/timing/stale → testes + harness/traces.
- Persistência → cenários de falha/transação.
- Pipeline crítico → evidência ponta a ponta.

**Segurança:** se houver divergência inesperada, não mascarar, não alterar o teste para fazê-lo passar, não assumir a implementação nova como correta. Investigar, classificar (bug/deliberada/convenção/falso positivo), documentar.

**Ferramentas e seus papéis:**
- **Graphify** → contexto estrutural; não valida comportamento.
- **OpenSpec** → registra intenção e mudança; não prova implementação.
- **Specs** → descrevem contrato/comportamento esperado; não substituem testes.
- **Git** → histórico e recuperação; não substitui validação.
- **Testes + harness** → evidência de execução; autoridade final sobre comportamento/performance.

**Integração com OpenSpec:** proposta → consultar specs existentes → implementar → validar por execução → atualizar specs se necessário → fechar mudança → commit/push.

## Referências

- `.opencode/skills/spreadhunter/SKILL.md` — use `skill spreadhunter` para regras completas + histórico de sessões (nota: contagem de testes no SKILL.md está desatualizada; validar com `--collect-only`)
- `.claude.md` — cópia parcial/desatualizada do AGENTS.md (regra #5 duplicada com numeração quebrada); ignorar e usar AGENTS.md como fonte autoritativa
- `docs/codigos_b3.md` — tabela completa de meses CALL/PUT + detecção de semanais (W em `cod[-2]` vs W de Nov PUT em `cod[4]`)
