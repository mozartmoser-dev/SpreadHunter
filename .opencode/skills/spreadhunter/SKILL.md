---
name: spreadhunter
description: |
  Spreadhunter — B3 options trading monitor (Python/PySide6/SQLite/RTD Profit).
  Scan, box spreads, collars, calendar collars, MPP prioritization.
  Critical: always confirm before changes, follow DB-first parametrization,
  never hardcode strikes, read MOD only from CALL leg.
license: MIT
compatibility: opencode
---

## Confirmação Obrigatória

**NUNCA aplique alterações sem antes apresentar a proposta ao usuário e obter
confirmação explícita.** Use `question` tool com opções claras de
aprovação/rejeição. O fluxo deve ser: proposta → confirmação → execução.

## Protocolo dos 7 Elos (investigação de dados)

Antes de concluir que um campo está ausente, atrasado, zerado ou divergente,
obrigatoriamente verificar a cadeia completa:

1. onde o campo é consumido;
2. onde deveria ser assinado no OpenFast;
3. se o tópico `(instrumento, campo)` está efetivamente registrado;
4. se o servidor entrega o campo quando assinado;
5. se o adapter recebe e armazena;
6. se o provider repassa o valor correto;
7. se o consumidor recebe e utiliza o mesmo valor.

Criar evidência/teste para cada elo relevante antes de propor uma correção.

**Não assumir que ausência de dado significa delay, divergência do feed ou
erro de cálculo sem antes verificar a assinatura e a entrega real do campo.**

## Stack

- **Linguagem**: Python 3.13.14 (`C:\Program Files\Python313\python.exe`)
- **UI**: PySide6 6.11.1 (QTableView, QAbstractTableModel, QSortFilterProxyModel)
- **Banco**: SQLite via sqlite3 (threading.local pool, `synchronous=NORMAL`,
  `cache_size=-8000`, `temp_store=MEMORY`)
- **RTD**: COM (win32com, pywin32 312) com Profit — `RTDProfit` em
  `src/infrastructure/providers/rtd_profit.py`
- **API externa**: opcoes.net.br (requests 2.34 + JSON API `OptionsChain`) em
  `src/infrastructure/integrations/opcoesnet_client.py`
- **Matemática**: scipy 1.17.1, numpy 2.4.6
- **Gráficos**: matplotlib 3.11.0 (backend qtagg)
- **Testes**: pytest 9.1.0 (442 testes)

## Estrutura de Pastas

```
src/
  application/use_cases/     — Lógica de negócio principal
  domain/entities/           — Entidades de domínio
  infrastructure/
    integrations/            — API clients externos
    persistence/
      database.py            — Conexão SQLite + PRAGMAs + seed params
      repositories/          — Repositórios (cache thread-safe com Lock)
    providers/               — RTD Profit provider
  ui/desktop/                — Telas PySide6
```

## Regras de Negócio Críticas

1. **Strike NUNCA é persistido** no banco. Strike vem exclusivamente do RTD
   em tempo real. `InstrumentoOpcional.strike` é fallback opcional em memória.

2. **MOD (tipo_opcao) só é lido da CALL**. PUTs na B3 são sempre Europeias
   (`E`). Só CALLs podem ser Americanas (`A`). O MOD deve ser extraído
   **apenas quando `tipo == "CALL"`**, em `importflash.py`.

3. **Parametrização Obrigatória**: todo valor de negócio (dias, %,
   limiares, timeouts) deve vir do banco. Fluxo:
   `database.py` (seed) → `parametro_operacional.py` (defaults)
   → `parametros_widget.py` (UI) → `regras_dialog.py` (exibição).

4. **Custos B3** usam prêmio da opção / preço da ação como base
   (NUNCA strike). Ida-e-volta (×2).
5. **Coerência do book** — regra absoluta: **quem vende recebe `bid_*`,
   quem compra paga `ask_*`**. Nunca inverter. Aplica-se a TODO cálculo:
   - Comprar ativo: paga **ask** (`of_venda_ativo`), NUNCA bid.
   - Vender ativo: recebe **bid** (`of_compra_ativo`), NUNCA ask.
   - Comprar opção: paga **ask** (`of_venda_*`).
   - Vender opção: recebe **bid** (`of_compra_*`).
   - **Atenção aos nomes:** `of_venda_*` = oferta de venda no book = ASK
     (você paga); `of_compra_*` = oferta de compra no book = BID (você
     recebe). Referem-se ao **lado do book**, não ao lado do trader.
   - Collar: `preco_compra_ativo` usa `of_venda_ativo` (ask) — correto
     ao comprar a ação. Inverter bid/ask → subestima capital → infla % CDI.

5. **Collar calendário**: aceita calls e puts ITM/ATM/OTM. Pareamento
   por distância de strike (`calendario_strike_diff_max`).

6. **RTD RefreshData com timeout**: `refresh(timeout_ms)` executa em thread
   separada com `CoInitialize()`. Timeout parametrizável
   (`rtd_refresh_timeout_ms`, seed=5000ms). Se exceder, pula o ciclo.

7. **Blacklist**: ativos na `black_list_import` são removidos do banco
   na importação (sem preservação). 53 ativos.

8. **Import único**: só ⚡ Importar (`importflash.py`). API `OptionsChain`
   para todas as séries (mensais + W1/W2/W3/W4).

9. **Códigos B3**: tabela completa de meses CALL/PUT + detecção de semanais
   em `docs/codigos_b3.md`. Regra: `W` em `cod[-2]` = semanal, `W` em
   `cod[4]` = PUT de Novembro (mensal). Nunca confundir.

## Convenções de Código

- Type hints obrigatórios em funções públicas
- `snake_case` para funções/variáveis, `PascalCase` para classes
- Imports: stdlib → third-party → local (separados por linha em branco)
- `@dataclass` para DTOs/resultados
- Repositórios: `get_by_chave()`, `save()`, `delete_all()`
- Thread safety: `threading.Lock` em caches de repositório
- Diálogos: `setup_ui()`, `atualizar_resultados()`

## Histórico de Sessões

### 17/06/2026 — 11 correções do novaavaliacao.md
- **BUG-002**: Filtro liquidez calendário (rejeita QUL≤0 em ambas pernas)
- **FIN-006**: Taxa contínua `log(1+r)` na paridade MPP
- **BUG-007**: `threading.local` usa hash md5 do path
- **FIN-003**: capital_empregado negativo não zera retornos (`abs()`)
- **FIN-001+BUG-001**: Pior retorno = strike_put, melhor = strike_call
- **BUG-004**: DELETE SQL com loop por código (correlated subquery não funciona no SQLite)
- **BUG-008**: pop_upside usa iv_call, pop_downside usa iv_put
- **BUG-009**: Score normaliza apenas viáveis
- **BUG-010**: `if be_baixa` → `is not None`
- Crash fim de semana: try/except no `np.busday_count`
- Snapshot MPP: contador agora incrementa corretamente (salva a cada 10 ciclos)
- **Box 4P**: `lucro = clr - distancia` é short box, fórmula correta
- **159/159 testes**

### 07/08/2026 — Lições aprendidas (timestamps + diagnóstico)

1. **Nunca culpar a fonte externa sem auditar o próprio código primeiro.**
   O `ts_ativo_ask` mostrava 43s/194s de atraso — parecia culpa do OpenFast.
   Mas a causa real era `tem_mudanca` em `mercado_data_provider.py:520-525`:
   `codigos_mudados` contém `PETR4` (push do ativo), mas o check só verificava
   `inst.cod_put` e `inst.cod_call` — NUNCA `inst.ativo`. Push do ativo sem
   push das opções → `cab_mudou = False` → CAB skip → `_precos_ativo_cache`
   mascara ASK=0 com valor antigo. O timestamp era real, o preço não.

2. **Caches de fallback mascaram zeros.** `_precos_ativo_cache` serve valor
   antigo quando o source retorna ASK=0. O timestamp avança mas o preço fica
   parado — inconsistência silenciosa. Ao auditar dados, SEMPRE verificar se o
   valor veio do cache ou da fonte fresca.

3. **Quando o usuário insiste que algo está errado, está.** Não importa se o
   código parece correto na inspeção visual — se os timestamps dizem 194s de
   atraso, há um problema real. Confiar na evidência, não na intuição.

4. **Features de auditoria (timestamps, debug) precisam de auditoria própria.**
   Implementar `ts_ativo_ask/bid` foi só metade do trabalho. A outra metade é
   rastrear TODO o fluxo (provider → monitor → DTO → UI) e verificar cada
   condição que pode distorcer o dado. Só expor o timestamp não basta — é
   preciso garantir que ele reflete o mesmo dado que está sendo exibido.

### 09/08/2026 — Instrumentação T1→T6 (diagnóstico STALE OpenFast)

**Ativação:** `SH_TRACE_CHAVE=COD|CAMPO` (ex.: `PETR44255|BID`); logs em
`logs/stale_trace.log` (pipe-delimited, buffered, thread-safe, só grava se a env
estiver setada). Instrumentação desligável — não altera lógica, apenas observa.

**Cadeia de timestamps:**
```
RCV|seq|ts_recv|nbytes        recv() da thread leitora (contador de sequência)
T1|seq|ts_recv|cod|campo|valor  linha SQT recebida (associada ao recv que a trouxe)
T2|cod|campo|valor             parse da linha concluído
T3|cod|campo|valor|ver         cache atualizado (_cache_ts/_cache_ver)
T4|cod|campo|valor             refresh() entregou a chave via dirty_keys
T5|cod|campo|valor|idade|stale  leitura: provider (montagem entrada) ou consumo
                                direto do use case (sufixo |UC)
T6|ctx|elapsed_s|UC            duração do estágio de cálculo (ctx = UC/varrer/total)
EVT|tipo|detalhe               conectar/SYN/assinar/rassinar/SYN/watchdog/
                                no_new_update/stale_skip/re_registrar...
```
UCs instrumentados com `log_consumo` (T5) + `log_t6` (T6): **BOX4P, PUT_RATIO,
MPP, COLAR, COLAR_CAL** (+ monitor_geral já existente).

**Mapa de interpretação — aonde o atraso NÃO aparece é onde está:**
- **A** — OpenFast não mandou: não aparece SQT/T1 para a chave, embora outras
  atualizações cheguem.
- **B** — problema na entrega/processamento: RCV presente, salto abissal até T1.
- **C** — parser/cache do adapter demorou: T1 → T2/T3 anormal.
- **D** — provider demorou: T3 → T4/T5 anormal.
- **E** — cálculo demorou: T5 → T6 anormal.
- **F** — **cadeia interna rápida, mas valor aparentemente velho**: a cadeia
  T1→T6 é curta, porém o valor recebido parece não representar o mercado atual.
  ⚠️ Isso **ainda não prova** que o OpenFast seja a origem — só exclui as perdas
  internas. A prova definitiva dependerá do timestamp de origem (TIME/TIMENEG),
  **se** o protocolo fornecer isso para SQT — a verificar no manual quando
  necessário.

**Plano para a próxima sessão:** rodar o trace em mercado aberto. Se reaparecer a
cotação com dezenas de segundos de atraso, a cadeia T1→T6 dirá exatamente onde os
segundos foram perdidos. Não alterar lógica enquanto a instrumentação estiver ativa;
remover `stale_trace` após o diagnóstico.

### 11/08/2026 — Patch OO → VEC no `varrer()` (BOX/SBTH) — CONCLUÍDO

- **Patch** `src/application/use_cases/monitor_oportunidades.py`: loop OO
  per-instrumento (`_calcular_oportunidade`) substituído por `CalculadoraVetorizada`
  + derivação vetorizada de todos os campos do DTO, preservando exatamente as regras
  da `CalculadoraBoxSbth` (classificação/operação por valores não-arredondados;
  custos arredondados 4/6 casas no DTO).
- **Equivalência OO × VEC comprovada campo-a-campo** — 38 campos do DTO idênticos
  (harness sintético + varredura de fronteira: 0 divergências no caminho escolhido).
- **689 testes passando**.
- **Benchmark real validado** (carga congelada de 51.060 chaves): ~1,402 s → ~1,007 s,
  ≈1,4× de speedup / ~28% de redução.
- **`vencimentos=None` mantido deliberadamente** para preservar a regra atual do OO
  (`dc_to_du` aproximado 252/365). VEC com vencimentos reais/calendário B3 **NÃO foi
  introduzido** (varredura de fronteira mostrou que mudaria classificação na fronteira).
- Commit `725dcd10305a938c009e9764b9a168035df3dc8b` — `perf: vetoriza montagem de
  DTOs do varrer() (BOX/SBTH) preservando regras do OO` — push concluído, `main`
  sincronizada com `origin/main`.

**Próximo passo (amanhã):**
1. Validar no mercado aberto com o protocolo T1–T6/Onda 1 existente. Comparar com o
   baseline histórico de 07/08 usando as mesmas métricas. Medir impacto no pipeline
   completo (retomada, varredura, tempo até disponibilidade da oportunidade, nº de
   instrumentos, stale data, comportamento do worker, CPU/memória). Verificar se a
   redução do benchmark aparece no comportamento real.
2. **Aplicar o skip da Onda 1 via `codigos_mudados` (§6 de `retomada_delay_openfast.md`)**
   — reclassificado pelo usuário para amanhã, logo após a validação. É o ganho certo
   grande: `onda1=1,002s` de `var=1,408s` (71% do ciclo é reconstrução redundante);
   `ref=0,023s` prova que o feed é rápido. Transforma o ciclo de `O(38k)` → `O(#mudanças)`
   (captura ~1,0–2,5s → ~0,1–0,2s) e reduz o `T3→T4`. Preservar: gate de frescor antes
   do skip, leitura sempre fresca de status/ativo/preço, e gravação de `_dados_cache`
   no ramo Onda 1 (ver `docs/verificacao_codigos_mudados.md`).

> ⚠️ **LEMBRETE PARA AMANHÃ (usuário pediu):** após concluir os testes/validação no
> mercado aberto, **lembrar o usuário** de que o skip da Onda 1 (§6) está agendado para
> ser aplicado em seguida — só implementar depois da confirmação explícita.

**Pendências separadas (NÃO fazer agora):**
- Investigação do crash Qt `tests/test_fase4.py::TestMonitorTableModel::test_tipo_opcao_display`
  (pré-existente, `0xC0000409`, não relacionado ao patch — confirmado em worktree limpo do HEAD).
- Estudo futuro da convenção CDI/B3 exata vs aproximação atual.
- Otimizações residuais, somente após a validação e o skip da Onda 1 no mercado aberto.
