# InstrumentoRepository

## Propósito

Repositório de leitura para `InstrumentoOpcional` — a entidade que mapeia pares (CALL, PUT)
para um ativo + vencimento na B3. É a tabela central de instrumentos: sem ela, nenhum use
case consegue montar estratégias porque não sabe quais opções existem para cada ativo.

**Papel real no sistema (descoberto via grep, 07/08/2026):** o `InstrumentoRepository` é um
repositório **somente de leitura** em produção. Os métodos de escrita (`save`, `save_batch`,
`delete_all`) existem como API pública mas **não são chamados por nenhum código de produção**.
O único write path real do sistema é o `importflash.py` (`scripts/validar_opcoes/importflash.py:145`),
que faz `DELETE FROM instrumentos_base` + `INSERT INTO instrumentos_base` diretamente via
SQL raw, contornando completamente o repositório. O ciclo de produção é:

```
importflash.py (SQL raw: DELETE + INSERT)     → escreve no banco
MonitorWorker.invalidate_cache()               → invalida cache da classe
Próximo get_all() / get_all_mapped()           → relê do banco, vê novos dados
```

Isso significa que `save()`, `save_batch()` e `delete_all()` são efetivamente **APIs
de conveniência para testes** (usadas apenas em fixtures `populated_db`) e **código
não exercitado** em produção. O contrato abaixo documenta o comportamento implementado,
mas a interpretação prática de "o que este módulo garante" foca nos métodos de leitura.

Cache compartilhado no nível de classe (`_cache_all`, `_cache_mapped`) com `threading.Lock`
— todas as instâncias compartilham o mesmo cache. Invalidação é forçada externamente via
`InstrumentoRepository.invalidate_cache()` (chamado pelo `MonitorWorker` a cada ciclo,
`monitor_worker.py:385`).

## Contrato (Requisitos)

> **Nota sobre métodos de escrita:** `save()`, `save_batch()` e `delete_all()` são APIs
> públicas documentadas abaixo, mas **não são exercitadas pelo fluxo de produção**.
> O `importflash.py` escreve direto no banco via SQL raw. Esses métodos existem apenas
> como conveniência para testes (fixtures `populated_db`). O contrato real do sistema
> é: o cache lê do banco o que o `importflash.py` escreveu, com `invalidate_cache()`
> como mecanismo de sincronização.

### `save(instrumento) -> InstrumentoOpcional`

**[API de teste — não usada em produção.]**

**Garante:**
1. Insere na tabela `instrumentos_base` com colunas `(ativo, cod_put, cod_call, vencimento, tipo_opcao)`.
2. `vencimento` é serializado via `.isoformat()` (ex: `"2026-08-21"`).
3. `tipo_opcao` é serializado via `.value` (enum: `"A"` ou `"E"`).
4. `strike` **NÃO é persistido** pelo repositório (a coluna existe no schema mas o
   `save()` não a inclui no INSERT — strike vem do RTD em tempo real, regra #1 do AGENTS.md).
5. Atribui `instrumento.id = cursor.lastrowid` e retorna o objeto mutado.
6. Invalida o cache de classe antes de abrir a conexão.

### `save_batch(instrumentos: list) -> int`

**[API de teste — não usada em produção.]**

**Garante:**
1. Usa `executemany` para inserção em lote.
2. **Não atribui IDs individuais** — diferente de `save()`, não itera para popular `instrumento.id`.
3. Retorna `len(rows)` (contagem de linhas afetadas).
4. Invalida o cache.

### `get_all() -> list[InstrumentoOpcional]`

**Garante:**
1. Retorna **cópia** da lista cached (`list(self._cache_all)`). O cache original nunca é exposto.
2. Se o cache está vazio, lê `SELECT * FROM instrumentos_base`, popula o cache sob lock, e retorna cópia.
3. Lê `strike` via `_row_strike()` — safe para DBs legacy sem a coluna.
4. Lê `created_at` opcionalmente (pode não existir em schemas antigos).

### `get_all_mapped() -> dict[tuple[str, str], InstrumentoOpcional]`

**Garante:**
1. Chave composta `(ativo, cod_put)` — mapeia cada PUT exclusivamente (evita confusão
   entre ativos com mesmo código de opção, ex: `PETRX80` pode existir em PETR4 e PETR3).
2. Retorna **cópia** do dict cached (`dict(self._cache_mapped)`).
3. Constrói o mapa a partir de `get_all()` (não de uma query separada).

### `get_by_ativo(ativo: str) -> list[InstrumentoOpcional]`

**Garante:**
1. Query direta sem cache (`WHERE ativo = ?`).
2. Retorna todos os vencimentos daquele ativo.

### `get_proximos_vencimentos(limite: int = 30) -> list[date]`

**Garante:**
1. `SELECT DISTINCT vencimento WHERE vencimento >= date('now') ORDER BY vencimento LIMIT ?`.
2. Retorna `list[date]` ordenado (ascendente), sem duplicatas.

### `delete_all() -> int`

**[API de teste — não usada em produção.]**

**Garante:**
1. `PRAGMA foreign_keys=OFF` antes do DELETE (evita cascade em tabelas filhas que referenciam `instrumentos_base`).
2. Invalida o cache.
3. Retorna `cursor.rowcount`.

### `invalidate_cache()` (classmethod)

**Garante:**
1. Sob `cls._lock`, zera `_cache_all` e `_cache_mapped` para `None`.
2. Pode ser chamado externamente — usado pelo `MonitorWorker` no início de cada ciclo
   para forçar refresh dos instrumentos após re-importação.

## Decisões Tomadas

### 1. Cache no nível de classe, não de instância

**Porquê:** O banco de dados é singleton por processo (`%APPDATA%/Spreadhunter/spreadhunter.db`).
Cache por instância seria redundante e inconsistente — uma instância não saberia que
outra instância fez `save()`. Cache de classe resolve isso com um `threading.Lock`.

**Trade-off:** Se duas threads usarem instâncias com `db_path` diferentes (ex: testes com
`tmp_path`), o cache de classe é compartilhado indevidamente. Isso não acontece em
produção (só um db_path), mas explica por que os testes usam `tmp_path` e `init_db`
fresh — o cache de classe pode conter dados do teste anterior se não for invalidado.

### 2. `_row_strike()` — safe extraction com fallback

**Porquê:** A coluna `strike` foi adicionada ao schema depois da criação inicial.
DBs legacy podem não tê-la. `_row_strike()` usa try/except `IndexError | KeyError`
para retornar `None` nesses casos, em vez de quebrar. Strike é tratado como
fallback opcional (`InstrumentoOpcional.strike: float | None`), nunca como fonte
primária — a fonte primária é o RTD.

### 3. `delete_all()` desliga foreign keys

**Porquê:** Tabelas como `oportunidades` têm `instrumento_id` FK → `instrumentos_base`.
Sem `PRAGMA foreign_keys=OFF`, o DELETE falharia se houver oportunidades referenciando
instrumentos. Na prática, como `delete_all()` só é chamado em testes (nunca em produção —
o `importflash.py` faz `DELETE FROM instrumentos_base` direto, também contornando FKs),
este PRAGMA existe como segurança para quem usar a API de teste.

### 4. `save_batch` não popula `instrumento.id`

**Porquê:** `executemany` do SQLite não retorna `lastrowid` por linha. Popular IDs
exigiria uma segunda query ou iteração. Como ninguém chama `save_batch()` em produção
(o `importflash.py` insere direto e não precisa dos IDs), o custo nunca se justificou.
Se um teste futuro precisar dos IDs, pode iterar com `save()` individual.

### 5. `get_all()` e `get_all_mapped()` retornam cópias

**Porquê:** O cache é mutável (list/dict). Se o chamador modificar a lista retornada
(ex: `get_all().append(...)`), o cache original não deve ser afetado. Retornar
`list(inst_list)` e `dict(mapped)` garante isolamento.

### 6. `get_by_ativo()` não usa cache

**Porquê:** O volume de chamadas por ativo é baixo (um por ativo na whitelist, a cada
ciclo do worker) e o cache `get_all()` já está populado em memória. Manter um segundo
nível de cache indexado por ativo adicionaria complexidade sem ganho real.

### 7. Invalidação externa — o verdadeiro ciclo de sincronização

**Porquê:** O `importflash.py` escreve direto no banco (`DELETE` + `INSERT` na tabela
`instrumentos_base`, linhas 145 e 152) sem nunca instanciar `InstrumentoRepository`.
Sem `invalidate_cache()`, o cache de classe conteria dados stale indefinidamente após
uma re-importação.

O `MonitorWorker` resolve isso chamando `InstrumentoRepository.invalidate_cache()`
no início de cada ciclo (`monitor_worker.py:385`). O ciclo completo de produção é:

1. Usuário clica "Atualizar" no `GradeOpcoesDialog`
2. `_ImportThread` roda `importflash.main()` que faz SQL raw: `DELETE` + `INSERT` na tabela
3. No próximo ciclo do worker, `invalidate_cache()` zera `_cache_all` e `_cache_mapped`
4. `get_all_mapped()` relê do banco, populando o cache com os novos instrumentos

Este é o **único** mecanismo que mantém o cache consistente com o banco em produção.
Os métodos `save()`/`save_batch()`/`delete_all()` do repositório também invalidam o cache,
mas como nunca são chamados em produção, esse caminho só é relevante em testes.

## Decisões Rejeitadas

### 1. Cache por `db_path` (chave de instância)

Rejeitado porque em produção só existe um banco. A complexidade de gerenciar
múltiplos caches por path não se justifica. Nos testes, o `tmp_path` isolado
+ `init_db` fresh garante que cada teste começa com cache limpo.

### 2. `get_all_mapped()` com chave `(ativo, cod_call)` também

Rejeitado porque a chave de mapeamento usada em todos os use cases é pela PUT
(`cod_put`). A CALL é localizada via `InstrumentoOpcional.cod_call` depois de
encontrar o instrumento pela PUT. Adicionar um segundo mapa seria redundante.

### 3. `strike` como coluna NOT NULL

Rejeitado porque strike NUNCA é fonte de verdade — vem do RTD. A coluna existe
apenas como conveniência (fallback) e para compatibilidade com ferramentas SQL.
Marcá-la como NOT NULL quebraria imports onde o RTD ainda não forneceu o strike.

### 4. `get_all()` com filtro de data (só vencimentos futuros)

Rejeitado porque o importador insere apenas séries vigentes (vencimento ≥ hoje).
Filtrar na query seria redundante e esconderia bugs de importação (ex: inserir
vencimento passado por engano).

## Dependências

- `sqlite3`, `threading` — stdlib
- `datetime.date`, `datetime.datetime` — stdlib
- `pathlib.Path` — stdlib (usado apenas no `_cache_key` do `ParametroRepository`, não no `InstrumentoRepository`)
- `src.domain.entities.instrumento_opcional` → `InstrumentoOpcional`, `TipoOpcao`
- `src.infrastructure.persistence.database` → `get_connection`

**Não depende de:**
- `json` (importado no topo do arquivo mas usado apenas por `OportunidadeRepository`, não por `InstrumentoRepository`)
- RTD/OpenFAST
- `calendario_b3`

**É dependência de:**
- 7 use cases em `src/application/use_cases/` (monitor_*)
- `src/infrastructure/providers/mercado_data_provider.py`
- `src/ui/desktop/grade_opcoes_dialog.py` (importação)
- `src/ui/desktop/monitor_worker.py` (invalidação de cache)
- `src/ui/desktop/colar_dialog.py`, `colar_calendario_dialog.py`, `dividendos_dialog.py`

## Cobertura de Teste

**Status: 2 testes em `tests/test_fase1.py`** (classe `TestInstrumentoRepository`)

| Teste | Cobre |
|---|---|
| `test_save_and_get` | `save()` + `get_all()`: ID populado, lista contém 1 item, ativo correto |
| `test_get_by_ativo` | `save()` (×2 ativos diferentes) + `get_by_ativo()`: filtro por ativo retorna só o ativo certo |

**Também exercitado indiretamente (fixtures):**
- `test_fase1.py`: `instrumento_repo` fixture usado por `TestOportunidadeRepository`, `TestEstruturaRepository`, `TestPernaRepository`
- `test_fase2.py`, `test_fase3.py`, `test_fase4.py`: `populated_db` fixtures que populam via `InstrumentoRepository.save()`
- `test_mercado_provider_openfast.py`: `populated_db` fixture

**Lacunas conhecidas (não cobertas):**
- `save_batch()` — 0 testes diretos
- `get_all_mapped()` — 0 testes diretos (embora seja o método mais chamado em produção: 12 call sites)
- `get_proximos_vencimentos()` — 0 testes
- `delete_all()` — 0 testes diretos
- `invalidate_cache()` — 0 testes diretos
- **⚠️ Concorrência multi-thread — 0 testes.** O inventory.md classifica este módulo como
  hotspot de concorrência (`threading.Lock` de classe, risco "Stale cache em multi-thread"),
  mas TODOS os testes são single-threaded. Nenhum teste exercita o cenário real de produção:
  `MonitorWorker` chamando `invalidate_cache()` enquanto use cases chamam `get_all_mapped()`
  simultaneamente. Confirmado via grep: zero ocorrências de `Thread(` ou `ThreadPoolExecutor`
  nos arquivos de teste relacionados a este módulo.
- `_row_strike()` com DB legacy sem coluna `strike` — 0 testes
- Comportamento com `created_at` ausente (schema antigo) — 0 testes
- `delete_all()` com foreign keys ativas (comportamento do `PRAGMA foreign_keys=OFF`) — 0 testes
