# WorkspaceSnapshot

## Propósito

Entidade que representa um snapshot completo do workspace do usuário:
parâmetros operacionais + configurações visuais (colunas, tamanhos, filtros).
Permite salvar/restaurar o estado completo da aplicação, incluindo snapshots
automáticos do sistema (`is_system=True`).

Suporta serialização bidirecional: para JSON (export/import de arquivo) e
para tupla de strings JSON (persistência no banco SQLite). A versão `system_default`
é criada automaticamente pelo bootstrap na primeira execução.

## Contrato (Requisitos)

### `WorkspaceSnapshot(id, nome, created_at, is_system, app_version, ...)`

**Garante:**
1. `id: int | None` — PK, `None` para snapshots ainda não persistidos.
2. `nome: str` — nome descritivo (ex: `"system_default"`, `"Meu Setup BOX"`).
3. `created_at: datetime` — timestamp de criação.
4. `is_system: bool` — `True` para snapshots automáticos do sistema (não
   aparecem na lista de snapshots do usuário).
5. `app_version: str` — versão do app que criou o snapshot (ex: `"2.1.0"`).
6. `parametros: dict[str, dict[str, Any]]` — dicionário de parâmetros
   operacionais. Chave = nome do parâmetro, valor = dict com detalhes.
   `field(default_factory=dict)`.
7. `workspace: dict[str, Any]` — configurações visuais (colunas, geometria,
   filtros, etc.). `field(default_factory=dict)`.

### `to_json() -> dict[str, Any]`

**Garante:**
1. Retorna dict com `schema_version: 1`, `app_version`, `saved_at` (ISO 8601),
   `nome`, `is_system`, `parametros`, `workspace`.
2. Compatível com export para arquivo `.json`.

### `from_json(payload) -> WorkspaceSnapshot` (classmethod)

**Garante:**
1. Constrói instância a partir de dict (import de arquivo `.json`).
2. `id=None` sempre (snapshots importados precisam de nova PK).
3. Campos ausentes recebem defaults seguros: `nome="Sem nome"`,
   `created_at=datetime.now()`, `is_system=False`, `app_version=""`,
   `parametros={}`, `workspace={}`.
4. Se `saved_at` ausente, usa `datetime.now()`.

### `serialize() -> tuple[str, str]`

**Garante:**
1. Retorna `(json.dumps(parametros), json.dumps(workspace))`.
2. Usa `ensure_ascii=False, sort_keys=True` para determinismo.
3. Formato usado pelo `WorkspaceSnapshotRepository` para persistir no banco.

### `deserialize(*, id, nome, created_at, is_system, app_version, parametros_json, workspace_json) -> WorkspaceSnapshot` (classmethod)

**Garante:**
1. Constrói instância a partir de colunas do banco SQLite.
2. Faz `json.loads()` de `parametros_json` e `workspace_json` com try/except
   para `ValueError | TypeError` — strings malformadas viram `{}`.
3. Valida que o resultado do parse é `dict` — se não for, usa `{}`.
4. Seguro contra corrupção de dados no banco: nunca levanta exceção.

### `SYSTEM_DEFAULT_NAME` (class constant)

**Garante:**
1. Valor: `"system_default"`.
2. Usado como `nome` do snapshot de sistema criado pelo bootstrap.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `__future__` | `annotations` | Habilita forward references (PEP 604) |
| `json` | `json` | `dumps`, `loads` para serialização |
| `dataclasses` | `dataclass`, `field` | Decorador, `default_factory` |
| `datetime` | `datetime` | Tipo do campo `created_at` |
| `typing` | `Any` | Tipo genérico para dicts internos |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 83 |
| Classes | 1 |
| Métodos/Funções | 4 (to_json, from_json, serialize, deserialize) + 1 constante de classe |
| Complexidade ciclomática estimada | Média (validação defensiva em deserialize) |
| Testes | Sim (via `WorkspaceSnapshotRepository` e testes de workspace) |

## Notas

- [2026-07-10 via git log] módulo criado. Sem modificações posteriores.
- `deserialize()` é notavelmente defensivo: 2 níveis de try/except + validação
  `isinstance(..., dict)`. Isso é intencional — snapshots podem vir de versões
  antigas do app com formatos diferentes, e o sistema nunca deve quebrar ao
  carregar um snapshot corrompido.
- `to_json()` usa `schema_version: 1` — não há mecanismo de migração de versão
  implementado. Se o formato mudar no futuro, snapshots antigos serão carregados
  com `deserialize()` defensivo (campos ausentes viram `{}`).
- `from_json()` sempre define `id=None` — snapshots importados de arquivo
  precisam de nova PK atribuída pelo repositório.
- `SYSTEM_DEFAULT_NAME = "system_default"` como constante de classe (não
  `ClassVar` do `typing`) — acessível como `WorkspaceSnapshot.SYSTEM_DEFAULT_NAME`.
