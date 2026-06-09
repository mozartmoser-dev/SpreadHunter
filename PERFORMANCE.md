# Diagnóstico de Performance — Varreduras RTD

## Sintoma

O sistema apresenta lentidão progressiva nos últimos dias. Os tempos de varredura
registrados nos logs mostram degradação consistente, principalmente nos **Fast scans**
(que deveriam ser ~0.1s por iterarem apenas instrumentos com book).

### Evolução temporal (média de Fast scan por log)

| Log (mais antigo → atual) | Fast avg | Global avg | Gargalos Global |
|---|---|---|---|
| spreadhunter.log.5 | 0.711s | 2.74s | 83% |
| spreadhunter.log.4 | 0.244s | 2.87s | 80% |
| spreadhunter.log.3 | 1.784s | 6.11s | 100% |
| spreadhunter.log.2 | 0.302s | 3.78s | 90% |
| spreadhunter.log.1 | 1.510s | 6.28s | 97% |
| spreadhunter.log (hoje) | 1.897s | 6.18s | 100% |

Fast avg subiu de **0.24s → 1.90s** — degradação de ~8x.

### Causa raiz identificada

O gargalo está no `RTDProfit.RefreshData(0)` — chamada COM síncrona ao Profit
que **não tem timeout exposto pelo Python**. Quando o Profit demora a responder 
(ou a conexão com o provedor de dados está lenta), o `RefreshData` segura o ciclo
inteiro.

Evidências:
- Fast scans variam de **0.000s** (instantâneo) a **6.880s** no mesmo arquivo de log
- Variação violenta → não é processamento Python (seria consistente)
- Todos os monitores são afetados igualmente (compartilham o mesmo `RefreshData`)
- A degradação é **progressiva através dos dias**, não correlacionada com nenhum commit

### O que NÃO é a causa

- Cache Python (`ler_campo_cache` é lookup de dict + float() — microssegundos)
- Algoritmos de cálculo (Box, SBTH, Collar, MPP — rodam em ms)
- Número de instrumentos (35k, similar aos dias anteriores)
- Monitor Collar Protetivo (já corrigido: não faz segunda chamada RTD)
- Mudanças de código recentes (revisadas commit a commit)

## O que já foi feito para mitigar

1. **Eliminada segunda chamada RTD no Collar** (`monitor_worker.py`):
   `_processar_colares` não chama mais `capturar_dados_mercado()` próprio.
   Garante exatamente 1 `RefreshData(0)` por ciclo.

2. **Global scan a cada 10 ciclos** (era 5): dobra o intervalo do scan
   completo, reduzindo pressão no RTD.

3. **Prioridade JSON**: persiste `_chaves_com_book` em disco. No startup,
   Onda 1 registra apenas os prioritários primeiros. Sistema útil em ~3
   ciclos em vez de ~18.

4. **Background scan**: 500 não-prioritários por ciclo global, sem bloquear
   o monitoramento.

5. **Staleness detection**: sinaliza "RTD Off" após 30s sem refresh ou
   3 ciclos sem dados (já estava, apenas ajustado).

## O que ainda pode ser tentado

### 1. Watchdog thread para RefreshData
Rodar o `RefreshData(0)` em uma thread separada com timeout. Se exceder
X segundos, aborta e retorna dados do cache anterior. Complexo pois
COM requer apartment threading.

### 2. RefreshData seletivo
Em vez de `RefreshData(0)` (todos os tópicos), usar `RefreshData(lista_de_tids)`
para refrescar apenas os tópicos dos instrumentos com book. Reduziria
drasticamente o volume.

### 3. Skip RefreshData quando ainda há cache fresco
Se o último refresh foi há <1s, pular — usar dados do cache. Arriscado
para dados de mercado em tempo real.

### 4. Log de diagnóstico por monitor
Adicionar timer individual para cada etapa do ciclo:
- `capturar_dados_mercado()` → quanto tempo dentro
- `monitor_uc.varrer()` → tempo de processamento
- Total do ciclo

---

## Prompt para retomada (AI context)

Você está analisando o SpreadHunter, um scanner de opções B3 em Python/PyQt5.
O sistema lê dados de mercado via COM RTD do Profit, processa ~35k instrumentos
por ciclo (2.5s), e exibe oportunidades (Box, SBTH, Collar, Box4P, MPP) em
painéis Qt.

O problema atual: `RTDProfit.RefreshData(0)` (COM call síncrona) está
degradando progressivamente — Fast scan médio subiu de 0.24s para 1.90s
em 6 dias. A causa externa (Profit, provedor, rede) está fora do nosso
controle, mas podemos mitigar com:

1. RefreshData seletivo (só tópicos com book)
2. Watchdog thread com timeout
3. Skip ciclos se cache ainda está fresco
4. Melhor diagnóstico por etapa do ciclo

Arquivos críticos:
- `src/infrastructure/providers/rtd_profit.py` — RefreshData, ler_campo_cache
- `src/infrastructure/providers/mercado_data_provider.py` — ciclo principal
- `src/ui/desktop/monitor_worker.py` — orquestrador dos monitores
- `src/infrastructure/providers/rtd_config.py` — campos RTD
- `scripts/diagnostic_scan.py` — análise de performance

Regras de negócio em `AGENTS.md`:
- **Strike é RTD-only. NUNCA persistir no SQLite.**
- CDI manual no DB, IR 15% swing trade, B3 costs fixos.
- Se RTD não fornecer strike, falhar ruidosamente.
