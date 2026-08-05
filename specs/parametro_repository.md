# ParametroRepository

## Propósito

Repositório de parâmetros operacionais centralizados no banco SQLite
(`parametros_operacionais`). É o ponto único de verdade para todo valor de
negócio do sistema: prêmios de risco, taxas, limites de strike, configurações de
estratégia e performance. Isola os consumidores (calculadoras, providers, UI) do
schema físico e provê cache thread-safe com invalidação explícita.

## Contrato (Requisitos)

1. `get_by_chave(chave: str) -> ParametroOperacional | None` retorna a entidade
   correspondente ou `None` se a chave não existir no banco. **Nunca** retorna
   fallback embutido — a responsabilidade do fallback é exclusiva do chamador
   (ex: `_ler_param_float` em `monitor_worker.py`).
2. `save(param)` faz `INSERT ... ON CONFLICT DO UPDATE` — **upsert atômico**.
   Nenhuma verificação prévia de existência; o valor novo sempre vence.
3. `seed_defaults()` insere parâmetros via `INSERT OR IGNORE` a partir de duas
   fontes em cascata:
   a. `config/parametros_default.json` (arquivo de blueprint do usuário)
   b. Hardcoded fallback em `database.py:_seed_parametros_colar()` (caso o JSON
      não exista ou falhe ao parsear)
   **Nunca sobrescreve** valor já existente — a primeira inserção vence.
4. `_fill_cache()` lê TODAS as linhas da tabela e tenta converter `valor` para
   `float`; se falhar, mantém como `str` (`fonte_market_data`, `bwb_modo`,
   `put_ratio_ratios`, whitelists/blacklists, paths de som, token Telegram).
5. Cache per-instância é lazy-filled na primeira chamada a `get_by_chave()` e
   invalidado por `save()` ou `seed_defaults()`.
6. Concorrência: lock por chave de cache (`self._cache_key()`) + lock de
   dicionário (`_dict_lock`) protegendo `_caches` e `_locks` em nível de classe.

### RISCO CONHECIDO: `INSERT OR IGNORE` + fallback assimétrico

O seed insere valores **apenas se a chave não existir**. Após o seed inicial, se
uma chave existir com valor numericamente incorreto (ex: `limite_protecao_pct`
gravado como `0.0099` em vez de `0.35`), **nenhum alarme é disparado**. O
`ParametroRepository.get_by_chave()` entrega o valor incorreto normalmente, e o
chamador (`_ler_param_float("limite_protecao_pct", 0.35)`) usa o valor do banco
porque `param is not None`. O fallback do código (`0.35`) nunca é atingido.

Isso já causou um bug de produção real em **20/07/2026** (commit `521454b`):
o parâmetro único/global `limite_protecao_pct` (então o único parâmetro de
orçamento de proteção, criado em `cbfb053` com valor correto `0.35`) teve seu
valor reduzido para `0.0099` no JSON de blueprint. O banco do usuário, criado a
partir desse JSON, carregou o valor incorreto silenciosamente. A proteção de
cauda ficou efetivamente desabilitada (~1% do ganho extra em vez de 35%).

**Nota cronológica:** os três parâmetros por variante
(`limite_protecao_pct_rendimento`, `_plato`, `_protecao`) foram criados **depois**
(commit `b9edc53`, 23/07/2026), já com os valores corretos (0.20, 0.45, 0.70)
nos hardcoded defaults — nunca tiveram o bug na origem. O JSON atual também
contém `0.0099` para eles, mas isso é resultado de uma segunda corrupção
posterior (commit `b9d7e9a`, 27/07/2026), independente do bug original. O
hardcoded fallback em `parametro_operacional.py` permanece correto para os 4.

**Mitigação:** sempre que adicionar ou alterar um valor de negócio em
`parametros_default.json`, verificar que o valor está correto **no banco do
usuário após o seed**, porque o JSON vence o hardcoded default da entity e o
`INSERT OR IGNORE` não corrige discrepâncias pós-seed.

## Decisões Tomadas

1. **Cache eager (lê tabela inteira).** `_fill_cache()` faz `SELECT *` sem
   `WHERE`. Motivo: a tabela tem ~120 linhas e é lida em quase todo ciclo do
   worker (centenas de `get_by_chave()` por iteração). Uma query por chave
   saturaria o SQLite. O cache evita IO após a primeira leitura.

2. **Conversão `float` com fallback `str`.** O schema armazena `valor TEXT`, mas
   ~95% dos parâmetros são numéricos. A conversão é tentada em `_fill_cache()`
   (não no `save()`) para centralizar a tipagem. Parâmetros string-like
   (`fonte_market_data`, whitelists) são armazenados como `str` no cache.

3. **`INSERT OR IGNORE` para seed, não `INSERT OR REPLACE`.** Decisão deliberada
   para preservar alterações do usuário via UI. O trade-off é o risco conhecido
   acima: valores incorretos no seed inicial nunca são corrigidos
   automaticamente.

4. **Cache por `_cache_key()` = path resolvido do banco.** Diferentes instâncias
   de `ParametroRepository` com o mesmo `db_path` compartilham o mesmo cache de
   classe (atributos `_caches` e `_locks` em nível de classe), mas instâncias com
   paths diferentes (ex: teste com `tmp_path`) têm caches independentes.

5. **`_dict_lock` separado dos locks per-cache.** Evita deadlock entre a
   criação do lock (que requer `_dict_lock`) e a operação dentro do lock (que não
   mexe em `_dict_lock`). O lock per-cache só é adquirido após `_dict_lock` ser
   liberado.

## Decisões Rejeitadas

1. **Fallback dentro do repositório.** Cogitou-se fazer
   `get_by_chave("taxa_cdi", default=0.1425)` com fallback no próprio repo.
   Rejeitado porque:
   - Fallbacks diferentes por chamador (ex: `_ler_param_float("perf_range_max",
     50.0)` vs `_ler_param_float("limite_protecao_pct", 0.35)`) poluiriam a
     assinatura.
   - A separação entre "buscar do banco" e "decidir o que fazer se não
     encontrou" é mais testável e explicita onde cada default mora.

2. **Validação de range no `save()`.** Cogitou-se rejeitar valores fora de
   ranges esperados (ex: `limite_protecao_pct` < 0 ou > 1). Rejeitado porque os
   ranges mudam entre versões e estratégias, e a validação precisaria de um mapa
   de regras que o repositório (camada de persistência) não deveria conhecer. A
   validação é responsabilidade da UI (`parametros_widget.py`).

3. **`INSERT OR REPLACE` no seed.** Rejeitado porque apagaria personalizações do
   usuário a cada inicialização — o seed roda em `init_db()` que é chamado em
   todo bootstrap.

## Dependências

- `sqlite3` (driver nativo, sem ORM)
- `database.get_connection()` (pool `threading.local`)
- `parametro_operacional.ParametroOperacional` (entidade de domínio)
- `threading.Lock` (concorrência per-chave + dicionário)
- `pathlib.Path` (resolução de `db_path` para cache key)

## Cobertura de Teste

**Status: Sim** (3 testes em `tests/test_fase1.py::TestParametroRepository`)

| Teste | Cobre |
|---|---|
| `test_seed_defaults` | `seed_defaults()` → `get_by_chave()` retorna valor esperado |
| `test_upsert` | `save()` ×2 na mesma chave → último valor vence |
| `test_get_by_estrategia` | `get_by_estrategia("BOX")` retorna subconjunto |

**Lacunas conhecidas (não cobertas):**
- Cache multi-instância com mesmo `db_path` (compartilhamento de `_caches`)
- Cache multi-instância com paths diferentes (isolamento)
- `_fill_cache()` com valor não-numérico (ex: `fonte_market_data = "openfast"`)
- Thread safety dos locks (testes são single-threaded)
- `list_all()` retornando todos os parâmetros
- Comportamento de `INSERT OR IGNORE` quando a chave já existe com valor
  diferente (não testa que o valor antigo é preservado)
