# WorkspaceService

## Propósito

Serviço de aplicação para snapshot e restauração do estado completo do workspace do usuário.
Persiste dois conjuntos de dados atômicos em uma única transação lógica: (1) parâmetros
operacionais do banco (`ParametroRepository`) e (2) estado da interface via QSettings
(ordem, visibilidade e largura de colunas das tabelas). Oferece exportação/importação de
snapshots como arquivos `.shwsp` e garantia de sistema default na inicialização.

**Papel real no sistema (descoberto via grep, 07/08/2026):** o `WorkspaceService` é
instanciado em 3 pontos de produção:
1. `bootstrap.py:20` — `garantir_system_default()` na inicialização do app, garantindo
   que existe um snapshot de fábrica para restauração.
2. `main_window.py:1535` — ações de "Salvar/Salvar como/Restaurar/Gerenciar Snapshots"
   no menu da janela principal.
3. `workspace_dialog.py:33` — diálogo dedicado de gerenciamento de snapshots (listar,
   renomear, apagar, exportar, importar, restaurar).

O serviço orquestra dois repositórios (`ParametroRepository` + `WorkspaceSnapshotRepository`)
e o `QSettings` do Qt, sendo a única classe do sistema que escreve simultaneamente no
banco e no registro do Windows.

## Contrato (Requisitos)

### `__init__(parametro_repo=None, snapshot_repo=None, db_path=None)`

**Garante:**
1. Aceita injeção de dependência opcional: se `parametro_repo` ou `snapshot_repo` não
   forem fornecidos, instancia com `db_path`.
2. `db_path` pode ser `None` — os repositórios usam `get_connection(None)` que infere
   o path padrão (`%APPDATA%/Spreadhunter/spreadhunter.db`).

### `ler_parametros_atuais() -> dict[str, dict[str, Any]]`

**Garante:**
1. Itera sobre `ParametroRepository.list_all()`.
2. Para cada parâmetro, tenta converter `valor` para `float`; se falhar, mantém como string.
3. Retorna dict no formato `{chave: {"valor": ..., "estrategia": ..., "descricao": ...}}`.
4. POSSÍVEL BUG — a conversão para `float` é lossy: se `valor` for `"10.0"`, vira `10.0`
   (`float`); se for `"10"`, vira `10.0`; se for `"abc"`, fica `"abc"` (`str`). Na
   restauração, `str(10.0)` → `"10.0"` vs original `"10"`. Pode causar falsos diffs
   em ferramentas de comparação de snapshots. Aguardando revisão.

### `ler_workspace_atual() -> dict[str, Any]`

**Garante:**
1. Lê todas as chaves em `_QSETTINGS_KEYS_CONHECIDAS` do `QSettings`.
2. Chaves são: `parametros/last_section`, `colunas_ocultas`, `colunas_ocultas_vendidas`,
   `colunas_ocultas_coberta`, `main_table_order`, `vendidas_table_order`,
   `coberta_table_order`, `colar_table_order`, `colar_cal_table_order`,
   `box_table_order`, `mpp_table_order`.
3. Ignora chaves com valor `None` (não inclui no dict de saída).
4. Captura exceções por chave (não interrompe o loop se uma chave falhar).
5. Usa `QSettings("Spreadhunter", "DesktopMonitor")` ou valores dos environment variables
   `SPREADHUNTER_QSETTINGS_ORG` / `SPREADHUNTER_QSETTINGS_APP` (para isolamento em testes).

### `criar_snapshot(nome: str) -> WorkspaceSnapshot`

**Garante:**
1. Cria snapshot com `parametros = ler_parametros_atuais()` e `workspace = ler_workspace_atual()`.
2. `created_at` = UTC now (`datetime.now(timezone.utc)`).
3. `is_system = False`.
4. `app_version = APP_VERSION` (constante `"Spreadhunter"` do `workspace_repository.py`).
5. Persiste via `WorkspaceSnapshotRepository.criar()` e retorna o snapshot com `id` populado.

### `restaurar(snapshot_id: int, chaves_a_ignorar: set[str] | None = None) -> None`

**Garante:**
1. Busca o snapshot por ID. Se não encontrado, levanta `ValueError`.
2. Se `chaves_a_ignorar` for fornecido, remove essas chaves do `workspace` antes de aplicar.
   Isso permite restaurar parâmetros sem sobrescrever certas preferências de UI.
3. Aplica parâmetros via `_aplicar_parametros()`.
4. Aplica workspace via `_aplicar_workspace()`.
5. POSSÍVEL BUG — `chaves_a_ignorar` filtra apenas o `workspace` (QSettings), não os
   `parametros`. Se a intenção é "ignorar colunas X", funciona; se for "ignorar parâmetro Y",
   não funciona. O nome do parâmetro é ambíguo. Aguardando revisão.

### `_aplicar_parametros(parametros: dict[str, dict[str, Any]]) -> None`

**Garante:**
1. Para cada chave no dict, instancia `ParametroOperacional` e chama `ParametroRepository.save()`.
2. `valor` é convertido para `str` via `str(valor)` se não for `None`.
3. `estrategia` default `"GERAL"`, `descricao` default `""`.
4. Captura exceções por parâmetro (não interrompe se um falhar).
5. Chama `ParametroRepository.invalidate_cache()` ao final.

### `_aplicar_workspace(workspace: dict[str, Any]) -> None`

**Garante:**
1. Para cada chave em `_QSETTINGS_KEYS_CONHECIDAS`:
   - Se presente no `workspace`: `qs.setValue(key, valor)`.
   - Se ausente: `qs.remove(key)`.
2. Captura exceções por chave (`setValue` pode falhar com tipos incompatíveis).
3. Chama `qs.sync()` ao final para persistir no registro do Windows.
4. Se `qs.sync()` falhar, a exceção é silenciosamente ignorada. POSSÍVEL BUG —
   falha silenciosa significa que o workspace pode não ser persistido sem feedback
   ao usuário.

### `garantir_system_default() -> WorkspaceSnapshot | None`

**Garante:**
1. Verifica se já existe snapshot com nome `"system_default"`.
2. Se não existe, cria um com `criar_system_default_se_ausente()`, capturando
   o estado atual do workspace.
3. Retorna o snapshot criado ou `None` se já existia.
4. Chamado exclusivamente no bootstrap (`bootstrap.py:20`).

### `exportar_arquivo(snapshot_id: int, destino: Path) -> Path`

**Garante:**
1. Busca snapshot por ID. Se não encontrado, levanta `ValueError`.
2. Garante extensão `.shwsp` no arquivo de destino (adiciona se ausente).
3. Cria diretórios pais se necessário (`mkdir(parents=True, exist_ok=True)`).
4. Serializa via `snapshot.to_json()` com `ensure_ascii=False` e `indent=2`.
5. Retorna o `Path` final do arquivo (com extensão corrigida).

### `importar_arquivo(origem: Path) -> WorkspaceSnapshot`

**Garante:**
1. Verifica existência do arquivo; se não existe, levanta `FileNotFoundError`.
2. Lê e desserializa via `WorkspaceSnapshot.from_json(payload)`.
3. Se `app_version` estiver vazio no payload, define como `APP_VERSION`.
4. Força `is_system = False` (snapshots importados nunca são de sistema).
5. **Dedup de nomes:** se já existe snapshot com o mesmo nome, renomeia para
   `"Nome Original (2)"`, `"Nome Original (3)"`, etc. via `_proximo_nome_livre()`.
6. POSSÍVEL BUG — `nome_original` é capturado antes da dedup (linha 188) mas
   nunca usado. Variável morta, possível leftover de logging removido.

## Decisões Tomadas

### 1. Snapshot atômico de duas fontes de dados heterogêneas (SQLite + QSettings)

**Porquê:** Os parâmetros operacionais vivem no banco SQLite; a ordem/visibilidade
de colunas vive no QSettings (registro do Windows). Para o usuário, "salvar workspace"
deve capturar ambos em um único ponto no tempo. O `WorkspaceService` é a única classe
que orquestra essa atomicidade lógica (não transacional — não há rollback se uma das
escritas falhar).

**Trade-off:** Não há transação distribuída entre SQLite e registro do Windows.
Se `_aplicar_parametros()` sucede mas `_aplicar_workspace()` falha (ou vice-versa),
o sistema fica em estado inconsistente. Na prática, falhas de QSettings são raras
(permissão de escrita no registro), então o risco é aceito.

### 2. `_QSETTINGS_KEYS_CONHECIDAS` como whitelist explícita

**Porquê:** QSettings é um key-value store sem schema. Sem whitelist, qualquer chave
escrita por qualquer parte do código seria capturada no snapshot, incluindo lixo de
testes ou chaves obsoletas. A whitelist garante que apenas o estado relevante da UI
é persistido.

**Trade-off:** Adicionar uma nova tabela com colunas persistidas requer atualizar
`_QSETTINGS_KEYS_CONHECIDAS`. Se o desenvolvedor esquecer, a nova tabela não terá
suas colunas salvas/restauradas. Idealmente isso seria documentado no guia de
contribuição ou validado em teste.

### 3. Lazy import de `ParametroOperacional` dentro de `_aplicar_parametros()`

**Porquê:** Evita import circular — `workspace_service.py` está em
`src/application/services/` e `ParametroOperacional` está em `src/domain/entities/`.
O import é feito dentro do método, não no topo do arquivo.

**Trade-off:** O import acontece a cada chamada de `_aplicar_parametros()`. Como
o módulo já está em `sys.modules` após o primeiro import, o custo é insignificante
(apenas lookup de dicionário).

### 4. Dedup de nomes na importação com sufixo numérico `(n)`

**Porquê:** Se o usuário importa o mesmo arquivo `.shwsp` múltiplas vezes, cada
importação cria um snapshot com nome único (`"Meu Setup"`, `"Meu Setup (2)"`,
`"Meu Setup (3)"`). Isso evita sobrescrita acidental e mantém histórico.

**Trade-off:** Se o usuário importa, renomeia, e importa de novo, o contador
recomeça do 2 — não há verificação de unicidade global, apenas contra o momento
da importação.

### 5. `system_default` como snapshot imutável de fábrica

**Porquê:** O usuário pode bagunçar parâmetros e colunas e precisar de um "reset".
O `system_default` é criado automaticamente no primeiro bootstrap e nunca é alterado
(protegido contra deleção pelo `WorkspaceSnapshotRepository.apagar()`). O usuário
sempre pode restaurar para o estado de fábrica.

### 6. Environment variables para isolar QSettings em testes

**Porquê:** `QSettings("Spreadhunter", "DesktopMonitor")` lê/escreve no registro
do Windows. Testes que usam esses valores poluiriam o registro do desenvolvedor.
As variáveis `SPREADHUNTER_QSETTINGS_ORG` e `SPREADHUNTER_QSETTINGS_APP` permitem
redirecionar para namespaces isolados (`DesktopMonitor_Tests`) que são limpos no
fixture `limpar_qsettings`.

## Decisões Rejeitadas

### 1. Snapshot incremental (só diferenças)

Rejeitado porque o volume de dados é pequeno (~30 parâmetros + 8 chaves QSettings,
total < 5 KB). A complexidade de diff/patch não se justifica frente à simplicidade
do snapshot completo.

### 2. Versionamento de schema do snapshot

Rejeitado na Fase 1. O campo `APP_VERSION` existe mas é a string fixa `"Spreadhunter"`,
não um número semver. A migração de snapshots entre versões não é tratada —
snapshots de versões futuras com chaves desconhecidas são importados com `from_json()`
que aceita qualquer payload. Se uma chave nova for adicionada ao `_QSETTINGS_KEYS_CONHECIDAS`,
snapshots antigos não a conterão, e na restauração ela será removida (`qs.remove(key)`).

### 3. Compressão do `.shwsp`

Rejeitado porque os arquivos são pequenos (< 10 KB). Adicionar `gzip` complicaria
a inspeção manual (usuário pode querer abrir o JSON para ver o que está salvo).

### 4. Criptografia do `.shwsp`

Rejeitado porque o arquivo não contém segredos — apenas parâmetros operacionais
(thresholds, taxas) e layout de colunas. Credenciais (`OPCOESNET_CPF`, etc.)
vivem no `.env`, não no workspace.

## Dependências

- `json`, `logging`, `os`, `pathlib.Path`, `typing.Any` — stdlib
- `PySide6.QtCore.QSettings` — framework UI (única dependência de Qt neste módulo)
- `src.domain.entities.workspace_snapshot` → `WorkspaceSnapshot`
- `src.infrastructure.persistence.repositories.workspace_repository` → `WorkspaceSnapshotRepository`, `APP_VERSION`
- `src.infrastructure.persistence.repositories.repositories` → `ParametroRepository`
- `src.domain.entities.parametro_operacional` → `ParametroOperacional` (lazy import)

**Não depende de:**
- RTD/OpenFAST
- Use cases de monitoramento

**É dependência de:**
- `src/infrastructure/persistence/bootstrap.py` (inicialização)
- `src/ui/desktop/main_window.py` (menu de snapshots)
- `src/ui/desktop/workspace_dialog.py` (diálogo de gerenciamento)
- `tests/test_workspace.py` (6+ testes)

## Cobertura de Teste

**Status: 6+ testes em `tests/test_workspace.py`**

| Área | Cobre |
|---|---|
| `QSETTINGS_ORG` / `QSETTINGS_APP` | Constantes de classe |
| `ler_parametros_atuais()` | Leitura de parâmetros com conversão float |
| `criar_snapshot()` | Criação de snapshot com nome |
| `restaurar()` | Restauração de parâmetros e workspace |
| `restaurar()` com `chaves_a_ignorar` | Filtro de chaves na restauração |
| `exportar_arquivo()` | Exportação para `.shwsp` |
| `importar_arquivo()` | Importação com dedup de nomes |
| `garantir_system_default()` | Criação do system default no bootstrap |

**Lacunas conhecidas (não cobertas):**
- `_aplicar_workspace()` com falha de `qs.sync()` — 0 testes
- `restaurar()` com snapshot inexistente (`ValueError`) — coberto indiretamente?
- `importar_arquivo()` com arquivo inexistente (`FileNotFoundError`) — 0 testes
- `importar_arquivo()` com JSON malformado — 0 testes
- `importar_arquivo()` com `app_version` vazio — 0 testes
- Concorrência (duas threads chamando `criar_snapshot()` simultaneamente) — 0 testes
- `_aplicar_parametros()` com `valor=None` — 0 testes
- `_aplicar_workspace()` com tipo incompatível no `setValue()` — 0 testes
- Integração com `main_window.py` e `workspace_dialog.py` — 0 testes de integração
