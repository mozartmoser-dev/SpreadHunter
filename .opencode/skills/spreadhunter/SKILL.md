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
