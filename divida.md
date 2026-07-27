# Dívida Técnica — Spreadhunter

> Auditoria estática (sem executar nada) realizada em **2026-07-08** após várias
> sessões prévias de auditoria (Sonnet, Gemini, GLM, DeepSeek) das últimas
> semanas. Cada achado abaixo foi **confirmado** por leitura do código-fonte e
> referenciado com `arquivo:linha` para navegação rápida.
>
> 383/383 testes passam — auditoria não reflete cobertura, e sim o que o código
> diz que faz.

---

## Legenda de severidade

- **🔴 CRÍTICO** — bug em caminho quente, gera erro/NameError ou descarta trabalho.
- **🟠 ALTO** — comportamento divergente do que a documentação AGENTS.md diz.
- **🟡 MÉDIO** — débito de manutenção, código morto ou desincronização leve.
- **🟢 BAIXO** — cosmético, comentário enganoso ou duplicação menor.

---

## 1. Bugs e Condições Críticas

### 1.1 🔴 CRÍTICO — `_obter_instrumentos_mapa()` retorna apenas 1 item por bug de indentação

- **Arquivo**: `src/application/use_cases/mpp_use_case.py:409-435`
- **Sintoma**: `MPPUseCase.calcular_instantaneo()` (linha 316) deveria devolver
  `list[BoxScore]` para **todos os pares elegíveis**, mas retorna no máximo
  uma caixa-escalar.
- **Causa**: indentação. O bloco `for r in rows:` contém 3 statements, e o
  `mapa[cod_put] = {...}` está **fora** do loop — só a última linha do
  `fetchall()` é registrada.

```python
# src/application/use_cases/mpp_use_case.py:419-432
rows = conn.execute("SELECT * FROM instrumentos_base").fetchall()
mapa = {}
for r in rows:
    cod_put = r["cod_put"]
    venc = r["vencimento"]
    if isinstance(venc, str):
        venc = date.fromisoformat(venc)
mapa[cod_put] = {                          # ← INDENTAÇÃO ERRADA
    "cod_put": cod_put, ...
}
```

- **Como reproduzir**: rodar `monitor_worker._processar_mpp` com ≥ 2 ativos na whitelist → `mpp_atualizados` emite no máximo um `BoxScore`.
- **Por que ninguém viu**: não há teste para `_obter_instrumentos_mapa` nem para `calcular_instantaneo()`.
- **Correção mínima**: tabular as 4 linhas finais para dentro do `for`.

---

### 1.2 🔴 CRÍTICO — `NameError: msg` na coleta de taxas de aluguel (sucesso)

- **Arquivo**: `src/ui/desktop/main_window.py:1867-1877`
- **Sintoma**: ao finalizar coleta via "Tx Alug." com `status="sucesso"`, é
  chamado `QMessageBox.information(self, "Taxa de Aluguel", msg)` sem que
  `msg` esteja definido no escopo da função — `UnboundLocalError` (=
  `NameError`) em produção.

```python
# src/ui/desktop/main_window.py:1872-1876
if status == "sucesso":
    self._status_left.setText("InvestSite: Coleta de taxas concluída!")
    self._status_left.setStyleSheet("color: {}; ...".format(Palette.GREEN))

    QMessageBox.information(self, "Taxa de Aluguel", msg)   # ← msg indefinido
    self._abrir_visualizar_taxas()
```

- **Por que não pega em testes**: o caminho "Taxa → Coleta → sucesso" não tem
  cobertura automatizada.
- **Como reproduzir**: configurar `taxa_aluguel_habilitado=1`, abrir menu Tx
  Alug., esperar coleta terminar.
- **Correção mínima**: substituir a referência por uma string literal
  (ex.: `f"{resumo.get('sucessos', 0)} sucessos / {resumo.get('falhas', 0)} falhas"`).

---

### 1.3 🟠 ALTO — Parâmetros `import_max_months` e `black_list_import` somem da UI

- **Arquivo**: `src/ui/desktop/parametros_widget.py:622-636` (`_SIDEBAR_ORDER`)
- **Sintoma**: ambos os parâmetros existem em
  `PARAMETROS_POR_ESTRATEGIA["IMPORTACAO"]:182-185` mas a estratégia
  `"IMPORTACAO"` **não está** em `_SIDEBAR_ORDER`. Resultado: a página
  não é renderizada no stack de páginas.
- **Impacto**: usuário não consegue editar **pela UI** o horizonte da
  importação (default 9) nem a blacklist desde a refatoração do widget
  em 07/07/2026. Mudanças só pelo SQL ou `config/spreadhunter.db`.
- **Correção mínima**: adicionar `"IMPORTACAO"` em `_SIDEBAR_ORDER` (entre `"SOM"` e `"BOX_4P"` ou onde melhor organizar visualmente).

---

### 1.4 🟠 ALTO — `tipo_opcao` MOD desconhecido descarta pares válidos na importação

- **Arquivos**:
  - `src/ui/desktop/main_window.py:1995-2001` (cópia inline em `_AtualizarTudoThread`)
  - `scripts/validar_opcoes/importflash.py:120-127`
- **Sintoma**: para cada `(ativo, vencto, strike)`, se `mod` ∈ {`A`, `E`} usa tipologia; se for qualquer outro valor (incluindo string vazia retornada pela API), executa `continue` — **perde o par inteiro**.
- **Conflito com AGENTS.md**: "PUTs são sempre Europeias. CALLs podem ser A/E. MOD deve vir do `r["mod"]` apenas quando `tipo == "CALL"`, PUT não sobrescreve." — a regra atual elimina silenciosamente pares sem MOD.
- **Correção mínima**: quando `mod` vazio, fazer fallback baseado no tipo:
  - PUT → forçar `EUROPEIA`;
  - CALL → consultar valor armazenado ou assumir `A`; ou manter `continue` mas registrar log dos pares perdidos.

---

### 1.5 🟡 MÉDIO — `_regras_param_map` referencia chave inexistente `premio_risco` em 3 estratégias

- **Arquivo**: `src/ui/desktop/regras_dialog.py:82, 96, 113`
- **Sintoma**: para `BOX`, `COLLAR_CALENDARIO` e `BOX_4P` o dicionário usa a chave `"premio_risco"`, mas a chave real no schema é
  `premio_risco_box`, `premio_risco_colar_calendario`, `box_premio_risco`. Em
  `_montar_regras_codigo:255-260`, `param_map.get("premio_risco")` retorna
  `None` e o `if valor is not None` filtra a linha → usuário vê o dialog
  sem a regra "Viabilidade: x CDI ≥ …".
- **Impacto**: documentação UI enganosamente incompleta. Nenhum cálculo afetado.
- **Correção**: renomear para `"premio_risco_box"` (BOX), `"premio_risco_colar_calendario"` (COLLAR_CALENDARIO) e `"box_premio_risco"` (BOX_4P).

---

### 1.6 🟡 MÉDIO — `monitor_vendidas` chama método inexistente (`calcular_custos_vendida`)

- **Arquivo**: `src/application/use_cases/monitor_vendidas.py:117, 155`
- **Sintoma**: `self._custos_b3.calcular_custos_vendida(...) if hasattr(self._custos_b3, "calcular_custos_vendida") else 0.0`. O método **não existe** em `CalculadoraCustosB3` (vide `src/domain/services/calculadora_custos_b3.py`). Cai sempre no `0.0` por causa do `hasattr`.
- **Impacto**: o DTO `OportunidadeVendida.custo` aparece zerado na UI/Box Vendida/SBTH Vendida — embora a linha mostre que era intenção cobrar custos B3 da estrutura.
- **Correção**: implementar `calcular_custos_vendida(...)` em `CalculadoraCustosB3` ou remover a chamada.

---

### 1.7 🟡 MÉDIO — Vetorização do BOX/SBTH é desperdiçada

- **Arquivo**:
  - `src/application/use_cases/monitor_oportunidades.py:159-187`
  - `src/domain/services/calculadora_vetorizada.py:32-120`
- **Sintoma**: `ResultadoVetorizado` é construído com arrays (`custo_box`,
  `custo_sbth`, `ganho_box`, `ganho_sbth`, `pct_cdi_*`, etc.) — mas em
  `monitor_oportunidades.py:185` o DTO é reconstruído via
  `calc_oo.calcular(dados)`, recalculando item-a-item (não vetorizado).
- **Impacto**: a `CalculadoraVetorizada` corre trabalho de numpy que **não é
  aproveitado** no caminho de saída. Apenas `indices_viaveis` é relevante —
  e mesmo assim o loop re-faz tudo.
- **Correção**: ou eliminar a CalculadoraVetorizada (código morto) ou usar
  diretamente os arrays para preencher `OportunidadeMonitor`.

---

### 1.8 🟡 MÉDIO — `refresh_seletivo()` é código morto

- **Arquivo**: `src/infrastructure/providers/rtd_profit.py:171-181`
- **Sintoma**: o método `refresh_seletivo(tids: list[int])` está definido
  mas não é chamado em nenhum lugar do projeto.
- **Correção**: remover ou começar a usar para reduzir RPC COM com muitos
  tópicos.

---

### 1.9 🟡 MÉDIO — `Prioridade_set` em formato antigo vs chave composta agrava risco silencioso

- **Arquivo**: `src/infrastructure/providers/mercado_data_provider.py:412`
- **Sintoma**: a lista de prioridade é salva com
  `f"{inst.ativo}|{inst.cod_put}"` desde a migração para chave composta,
  mas o `Carregar prioridades` é compatível com a forma antiga (`cod_put`
  puro). A pendência está documentada em AGENTS.md mas não foi resolvida.
- **Impacto**: o `Onda 1` pode trazer **muitos** ativos a mais que o
  desejado — todos com código coincidente com os da whitelist antiga
  serão pegos.
- **Correção**: uma migração única no `_carregar_prioridades` que converte
  chaves que não contêm `|` para o composto, ou recriar a chave
  forçando o uso de `(ativo, cod_put)`.

---

### 1.10 🟡 MÉDIO — `_on_coleta_taxa_finished` promete sucesso silencioso

- **Arquivo**: `src/ui/desktop/main_window.py:1871-1876`
- **Sintoma**: ramificação `else` trata "erro" com `QMessageBox.critical`,
  mas a ramificação `if status == "sucesso"` referencia `msg` indefinido
  (item 1.2). Como `ColetarTaxasAluguelUseCase.executar()` (em
  `coletar_taxas_aluguel.py:38`) retorna sempre
  `{"status": "sucesso", ...}`, **qualquer coleta com falha passa a ser
  sucesso** na UI e ainda dispara o erro da 1.2.
- **Correção**: corrigir 1.2 e propagar corretamente o status real.

---

## 2. Dívida Estrutural / Manutenção

### 2.1 🟠 ALTO — Algoritmo de ⚡ Importar duplicado

- **Arquivos**:
  - `src/ui/desktop/main_window.py:1917-2027` (inline em `_AtualizarTudoThread`)
  - `scripts/validar_opcoes/importflash.py:82-127`
- **Sintoma**: corpo do importflash está **copiado literal** em
  `main_window.py`. Mudanças corretivas (ex.: fix do MOD desconhecido,
  1.4) precisam ser feitas em **duas** frentes.
- **Correção**: extrair para um use case `ImportarOpcoesNetUseCase`
  reutilizável ou função pura.

---

### 2.2 🟡 MÉDIO — Inconsistência entre `database.py` e `config/parametros_default.json`

- **Arquivo**: `src/infrastructure/persistence/database.py:97-217`
- **Sintoma**: o seed fallback inline (quando `parametros_default.json`
  não está presente) **omite** chaves críticas que existem em
  `PARAMETROS_DEFAULT` do `parametro_operacional.py`:
  - `taxa_registro_pct` (0.0001)
  - `taxa_iss_pct` (0.0)
  - `notif_telegram_enable`, `telegram_bot_token`, `telegram_chat_id`
  - `elegibilidade_strike_max_pct`
  - ranking_peso_colar_* (embora seed exista)
  - `box_qtd_min`, `box_soh_europeia`
  - `elegibilidade_strike_max_pct`
  - Seeds MPP na lista `mpp_params` (linha 152-183) e `perf_params` (linha 184-212) **não seed-a muitas chaves** que o `regras_dialog.py:219-220` espera exibir.
- **Impacto**: dependendo da forma de empacotamento (.exe sem `config/`),
  parâmetros B3 adicionais (taxa de registro e ISS) ficam com valor 0.0 →
  custo B3 sub-dimensionado. **Lentamente silencioso.**
- **Correção**: deixar `_seed_parametros_colar` chamar
  `ParametroOperacional.defaults()` que centraliza a lista, em vez de
  manter 3 listas (params, mpp_params, perf_params) duplicadas.

---

### 2.3 🟡 MÉDIO — Comentário de periodicidade de manutenção errado

- **Arquivo**: `src/ui/desktop/monitor_worker.py:554-571`
- **Sintoma**:
  - Linha 554: `if self._manutencao_cycle % 2 != 0` executa a cada
    **2 ciclos**. Com `msleep(3000)` é 6s, não "5s" que o comentário da
    AGENTS.md sugere.
  - Linha 567-568: `if self._manutencao_cycle % 1440 == 0` →
    1440 ciclos × 6s = 144 min. Comentário diz "≈ 60 min" (errado; deveria
    dizer ~2h24).
- **Correção**: ajustar os comentários para refletir o comportamento real ou alterar o divisor.

---

### 2.4 🟡 MÉDIO — `item_todos = QListWidgetItem("TODOS")` em duas dialogs

- **Arquivos**:
  - `src/ui/desktop/colar_dialog.py:2057`
  - `src/ui/desktop/colar_calendario_dialog.py:1842`
- **Sintoma**: o sentinel `"TODOS"` (string mágica) é reusado em duas
  dialogs. Cria acoplamento implícito — se renomear em uma, quebra a outra.
- **Correção**: extrair constante `SELETOR_TODOS = "TODOS"` em um módulo
  comum (`ui.desktop.constants` ou similar).

---

### 2.5 🟢 BAIXO — Função `calda` do MonitorWorker usa shadowing de `delta_total`

- **Arquivo**: `src/ui/desktop/monitor_worker.py:443-481`
- **Sintoma**: ao montar `ResultadoColarCalendario`("Cauda"),
  `delta_total=r.delta_total`. Como `ResultadoCaudaAssincrona` não retorna
  `delta_total`, este campo da variante Cauda é o mesmo da base (não
  recalculado para o ratio). Pode não refletir a estrutura com N CALLs.
- **Impacto**: exibição de `delta_total` na Cauda é informativo, não
  bloqueante — nenhum cálculo depende dele.
- **Observação**: nenhum teste cobre este caminho.

---

### 2.6 🟢 BAIXO — `parametros_operacionais.chave UNIQUE NOT NULL` + `valor TEXT`

- **Arquivo**: `database.py:374-380`
- **Sintoma**: `valor TEXT` para números (`"0.7"`, `"-70"`) força
  `float(val_raw)` em todas as leituras (`repositories.py:238`). Sem
  validação semântica (uma chave pode virar `0.7` ou `"foo"`).
- **Impacto**: silencioso. Mas a parametrização fica frágil se
  alguém salvar string em chave numérica.
- **Observação**: muitos sistemas fazem isso, é débito maduro — não
  bloquear, mas considerar CHECK constraints.

---

### 2.7 🟢 BAIXO — `_FiltroManutencao` em `main.py:45-47` usa substring hard-coded

- **Arquivo**: `main.py:45-49`
- **Sintoma**: lista de substrings (`"Manutenção"`, `"Ciclo:"`, etc.) para
  filtrar log profile. Esquecer de atualizar quando se renomear um log no
  worker faz o profile ficar silencioso.
- **Correção**: usar `logging.LogRecord.name`/marker explícito em vez de substring em `record.msg`.

---

### 2.8 🟢 BAIXO — `QProcess` importado mas nunca usado

- **Arquivo**: `src/ui/desktop/main_window.py:14`
- **Sintoma**: `from PySide6.QtCore import Qt, QTimer, QSize, QProcess, ...`. `QProcess` foi removido da automação PNT quando se migrou para `QThread` interno, mas o import ficou.
- **Correção**: remover `QProcess` do import.

---

### 2.9 🟢 BAIXO — Log DEBUG global e arquivo `pyarmor.bug.log` commitado

- **Arquivos**:
  - `main.py:12-24` — `logging.basicConfig(level=logging.DEBUG, ...)` em
    produção. Polui `logs/spreadhunter.log` rapidamente e traz custo de IO.
  - `pyarmor.bug.log` — log de trial PyArmor commitado no repo (root).
- **Sintoma**: developmental artifacts devem ficar fora do controle de
  versão.
- **Correção**: `level=INFO` por padrão, DEBUG opcional via flag/ENV. Adicionar `pyarmor.bug.log` ao `.gitignore` (ou remover do repo).

---

### 2.10 🟢 BAIXO — Acoplamento entre `ParametroOperacional.PARAMETROS_DEFAULT` (entidade) e `database.py` + `parametros_default.json`

- **Sintoma**: três pontos definem os defaults: a dataclass, o seed fallback
  inline e o JSON. Para cada novo parâmetro, todos três precisam ser
  atualizados, caso contrário o sistema diverge em bancos legados.
- **Correção**: tornar `database.py:_seed_parametros_colar` consumir
  somente `ParametroOperacional.defaults()`.

---

### 2.11 🟢 BAIXO — `monitor_colares_calendario.bind_monitor_signals` (sinais do widget)

- **Arquivo**: `src/ui/desktop/main_window.py:1058`
- **Sintoma**: `widget.bind_monitor_signals(self._worker)` é baseado na
  refatoração Tranche 3 (07/07). Cobertura de teste nula; nenhum teste
  para `bind_monitor_signals` ou `_count_viaveis_box_sbth`.
- **Precaução**: garantir que contador `BOX_SINTETICO` filtra corretamente
  `BOXSBTH` (vide também 1.7). Lógica atual aceita `"BOX" in "BOXSBTH"` →
  pode sobre-subcontar.

---

## 3. Pendências pouco confiáveis

| # | Item | Arquivo | Detalhe |
|---|------|---------|---------|
| P1 | Migração do formato antigo de `prioridade_set` | `mercado_data_provider.py` + `config/spreadhunter_prioridade.json` | hipótese "tenta ambos" funciona, mas qualidade fica opaca |
| P2 | Validar se o Profit usa `dc_to_du_exato` ou `aproximado` para IV | `calculadoras de spread` | híbrido hoje usa `aproximado` via `dias_corridos`. Vide AGENTS.md. |
| P3 | RTD não funciona em `.exe` compilado (PyInstaller) | `docs/DISTRIBUICAO.md:74-92` | documentado, não resolvido |

---

## 4. Resumo por severidade

| Severidade | # de itens |
|------------|------------|
| 🔴 CRÍTICO | 2 (1.1, 1.2) |
| 🟠 ALTO | 3 (1.3, 1.4, 2.1) |
| 🟡 MÉDIO | 8 (1.5-1.10, 2.2-2.4, 2.11) |
| 🟢 BAIXO | 6 (2.5-2.10) |
| **TOTAL** | **19** |

---

## 5. Próximas auditorias sugeridas

- Validar manualmente cada caminho do "Importar Opções + ⚡ Atualizar Tudo" para confirmar 1.4 e o MOD desconhecido.
- Auditar `monitor_worker` + sinais cruzados (boxing/cola_calendario/cauda MPP) — ver se há deadlock em thread-ui interações (vide 1.7 e o uso de sinais via `lambda` em `parametros_widget.bind_monitor_signals:1010-1039`).
- Micro-benchmark da vetorização desperdiçada (item 1.7). Ganho estimado
  alto se corrigida.

---

> **Aviso**: este arquivo é **apenas diagnóstico** — não há patches automáticos
> aplicados. Cada item acima é uma entrada pronta para virar issue/PR.
