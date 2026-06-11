---
name: spreadhunter
description: |
  Spreadhunter — B3 options trading monitor (Python/PyQt5/SQLite/RTD Profit).
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

- **Linguagem**: Python 3.12+
- **UI**: PyQt5 (QTableView, QAbstractTableModel, QSortFilterProxyModel)
- **Banco**: SQLite via sqlite3 (threading.local pool, `synchronous=NORMAL`,
  `cache_size=-8000`, `temp_store=MEMORY`)
- **RTD**: COM (win32com) com Profit — `RTDProfit` em
  `src/infrastructure/providers/rtd_profit.py`
- **API externa**: opcoes.net.br (requests + JSON API `OptionsChain`) em
  `src/infrastructure/integrations/opcoesnet_client.py`
- **Testes**: pytest (140 testes, sem skip)

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
  ui/desktop/                — Telas PyQt5
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

5. **Collar calendário**: aceita calls e puts ITM/ATM/OTM. Pareamento
   por distância de strike (`calendario_strike_diff_max`).

6. **RTD RefreshData com timeout**: `refresh(timeout_ms)` executa em thread
   separada com `CoInitialize()`. Timeout parametrizável
   (`rtd_refresh_timeout_ms`, seed=5000ms). Se exceder, pula o ciclo.

7. **Blacklist**: ativos na `black_list_import` são removidos do banco
   na importação (sem preservação). 53 ativos.

8. **Import único**: só ⚡ Importar (`importflash.py`). API `OptionsChain`
   para todas as séries (mensais + W1/W2/W3/W4).

## Convenções de Código

- Type hints obrigatórios em funções públicas
- `snake_case` para funções/variáveis, `PascalCase` para classes
- Imports: stdlib → third-party → local (separados por linha em branco)
- `@dataclass` para DTOs/resultados
- Repositórios: `get_by_chave()`, `save()`, `delete_all()`
- Thread safety: `threading.Lock` em caches de repositório
- Diálogos: `setup_ui()`, `atualizar_resultados()`
