Pendências 04/08/2026:

## Prompt original (metodologia OpenSpec)
salvo em: specs/SESSAO_OPENSPEC_PROMPT.md

## Tarefas

1. Commit da integração da salvaguarda (monitor_worker.py + main_window.py) — diff já revisado, pronto
2. Commit do parametros_widget.py (spinner perf_range_max 0-999) — sessão SBTH comprada
3. Spec do módulo 2: CalculadoraProtecaoCauda (src/domain/services/calculadora_protecao_cauda.py)
   - Fila: CalculadoraProtecaoCauda → CalculadoraCaudaAssincrona → InstrumentoRepository
   - specs/inventory.md já aprovado como base
   - Regra de atomicidade: 1 módulo por vez, parar após cada um, aguardar aprovação

## Entregas concluídas hoje
- specs/parametro_repository.md (aprovada)
- specs/inventory.md (aprovada)
- scripts/verificar_integridade_params.py (commit 72e4e7d)
- tests/test_verificar_integridade_params.py (commit 72e4e7d)
- Correção de 6 parâmetros corrompidos no JSON e banco (commit b9d7e9a)
- Integração da salvaguarda no worker + UI (pendente commit)
