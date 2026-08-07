# WorkspaceSnapshotRepository

Repositório para snapshots de workspace (tabela `workspace_snapshots`). Persiste e recupera configurações completas do aplicativo (parâmetros + workspace) serializadas como JSON, com suporte a snapshot de sistema imutável (não pode ser apagado).

## Contrato (Requisitos)

### `__init__(db_path=None)`
**Garante:**
1. Armazena `db_path`.

### `listar() -> list[WorkspaceSnapshot]`
**Garante:**
1. `SELECT * ORDER BY is_system DESC, created_at DESC` — snapshots de sistema primeiro, depois por data.

### `obter(snapshot_id: int) -> WorkspaceSnapshot | None`
**Garante:**
1. `SELECT * WHERE id = ?`. Retorna `None` se não encontrado.

### `obter_por_nome(nome: str) -> WorkspaceSnapshot | None`
**Garante:**
1. `SELECT * WHERE nome = ?`.

### `criar(snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot`
**Garante:**
1. Serializa `parametros` e `workspace` via `snapshot.serialize()` (método da entidade).
2. Insere com colunas: `nome`, `created_at`, `is_system` (0/1), `app_version`, `parametros_json`, `workspace_json`.
3. `created_at` usa `.isoformat()` se for `datetime`, senão `datetime.now(timezone.utc)`.
4. Atribui `snapshot.id = cursor.lastrowid`.

### `renomear(snapshot_id: int, novo_nome: str) -> None`
**Garante:**
1. `UPDATE SET nome = ? WHERE id = ?`.

### `apagar(snapshot_id: int) -> bool`
**Garante:**
1. Busca o snapshot primeiro.
2. Se `is_system`, bloqueia a remoção (loga warning e retorna `False`).
3. Se não for sistema, `DELETE WHERE id = ?`.
4. Retorna `True` se deletou.

### `existe_system_default() -> bool`
**Garante:**
1. Verifica se existe snapshot com nome `WorkspaceSnapshot.SYSTEM_DEFAULT_NAME`.

### `criar_system_default_se_ausente(parametros: dict, workspace: dict) -> WorkspaceSnapshot | None`
**Garante:**
1. Se já existe system default, retorna `None` sem fazer nada.
2. Cria `WorkspaceSnapshot` com `is_system=True`, `nome=SYSTEM_DEFAULT_NAME`, `created_at=datetime.now(timezone.utc)`.
3. Salva via `criar`.

### `_row_to_snapshot(row) -> WorkspaceSnapshot` (static)
**Garante:**
1. Converte `created_at` (string ou datetime) para `datetime`.
2. Se `created_at` for string inválida, usa `datetime.now(timezone.utc)` como fallback.
3. Reconstrói via `WorkspaceSnapshot.deserialize()` que faz `json.loads` dos campos JSON.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `datetime` | `datetime`, `timezone` | Timestamps |
| `pathlib` | `Path` | Type hint |
| `src.domain.entities.workspace_snapshot` | `WorkspaceSnapshot` | Entidade |
| `src.infrastructure.persistence.database` | `get_connection` | Conexão SQLite |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 144 |
| Última modificação | 2026-07-10 |
| Classes | 1 (`WorkspaceSnapshotRepository`) |

## Notas

- 2026-07-10 — última modificação.
- Snapshots de sistema (`is_system=True`) são imutáveis — `apagar` bloqueia a remoção. Isso protege o "System Default" de ser acidentalmente deletado.
- A serialização/deserialização é delegada à entidade `WorkspaceSnapshot` (`.serialize()` / `.deserialize()`), mantendo o repositório focado em SQL.
- `app_version` é a constante `"Spreadhunter"` (definida no topo do módulo).
