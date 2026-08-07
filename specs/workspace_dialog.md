# WorkspaceDialog

## Proposito

Dialogo de gerenciamento de workspaces -- salvar e restaurar snapshots que contem parametros do banco + ordem de colunas das tabelas. Lista snapshots com indicador visual de sistema (escudo) vs usuario. Suporta salvar, restaurar, apagar, exportar (.shwsp) e importar snapshots. Restauracao e imediata e notifica o `MainWindow` para recarregar parametros e colunas.

## Contrato (Requisitos)

### `_carregar_lista()`
**Garante:**
1. Lista snapshots do `WorkspaceService._snapshot_repo_inst().listar()`.
2. Snapshots de sistema (`is_system=True`) exibidos com prefixo de escudo e fonte em negrito.
3. Tooltip: "Snapshot de sistema -- criado na primeira execucao. Nao pode ser apagado."
4. Snapshots de usuario exibidos com prefixo de 3 espacos.
5. Seleciona o primeiro item automaticamente.

### `_salvar_atual()`
**Garante:**
1. Abre `QInputDialog.getText` para nome do snapshot.
2. Chama `WorkspaceService.salvar_snapshot_atual(nome)` que:
   - Le todos os parametros do banco.
   - Le ordem/largura de colunas de todas as tabelas (main, vendidas, coberta, colar, colar_calendario, box, mpp).
   - Persiste como `WorkspaceSnapshot` no banco.
3. Recarrega a lista.

### `_restaurar_selecionado()`
**Garante:**
1. Confirmacao via `QMessageBox.question`.
2. Chama `WorkspaceService.restaurar_snapshot(snap)` que:
   - Aplica parametros salvos no banco.
   - Restaura ordem/largura de colunas.
3. Emite `restaurar_solicitado.emit(snap.id)`.
4. Se houver incompatibilidade de colunas (detectada via `detectar_incompatibilidade`), exibe alerta.

### `_apagar_selecionado()`
**Garante:**
1. Snapshots de sistema NAO podem ser apagados (botao desabilitado).
2. Confirmacao antes de deletar.
3. Chama `WorkspaceService.apagar_snapshot(snap.id)`.
4. Recarrega a lista.

### `_exportar_selecionado()`
**Garante:**
1. Abre `QFileDialog.getSaveFileName` com filtro "*.shwsp".
2. Serializa snapshot como JSON e salva no arquivo.

### `_importar_arquivo()`
**Garante:**
1. Abre `QFileDialog.getOpenFileName` com filtro "*.shwsp".
2. Le JSON do arquivo, desserializa como `WorkspaceSnapshot`.
3. Salva no banco via `WorkspaceService.importar_snapshot(snapshot)`.
4. Recarrega a lista.

### `_snapshot_selecionado() -> WorkspaceSnapshot | None`
**Garante:**
1. Obtem o item selecionado na lista.
2. Extrai `Qt.UserRole` como snapshot ID.
3. Busca na cache local `_snapshots` ou, se nao encontrado, no repositorio.

### `_on_selecionado()`
**Garante:**
1. Exibe detalhes do snapshot no `QTextEdit`: nome, data de criacao, quantidade de parametros, tabelas incluidas.
2. Habilita/desabilita botoes conforme o tipo (sistema vs usuario).

## Dependencias Diretas (por import)

| Modulo | Simbolo | Uso |
|---|---|---|
| `pathlib` | `Path` | (importado, uso nao localizado no trecho lido) |
| `PySide6.QtCore` | `Qt, Signal` | Sinais e constantes |
| `PySide6.QtGui` | `QFont, QShortcut, QKeySequence` | Fonte e atalhos |
| `PySide6.QtWidgets` | `QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget` | UI framework |
| `src.application.services.workspace_service` | `WorkspaceService` | Servico de workspace |
| `src.domain.entities.workspace_snapshot` | `WorkspaceSnapshot` | Entidade |
| `src.ui.desktop.column_utils` | `detectar_incompatibilidade` | Validacao de colunas |

## Metricas

| Linhas | 343 |
| Classes | 1 |
| Testes | Nao |

## Notas

- **Shortcuts:** `Ctrl+Shift+S` (salvar), `Ctrl+Shift+R` (restaurar) -- registrados no escopo do dialogo.
- **Extensao `.shwsp`:** Formato proprietario de exportacao -- JSON serializado do `WorkspaceSnapshot`.
- **Snapshots de sistema:** Criados automaticamente na primeira execucao do `bootstrap`. Marcados com `is_system=True`, nao podem ser apagados pelo usuario -- servem como backup de fabrica.
- **`detectar_incompatibilidade`:** Verifica se a configuracao de colunas atual e compativel com a do snapshot. Se incompativel (ex: colunas foram adicionadas/removidas entre versoes), alerta o usuario mas permite restaurar assim mesmo (so parametros serao aplicados).
- **`_snapshot_repo_inst()`:** O `WorkspaceService` expoe um metodo "privado" para acesso ao repositorio -- `_snapshot_repo_inst()`. Isso e um padrao de conveniencia que quebra encapsulamento. POSSIVEL BUG -- NAO CORRIGIDO, aguardando revisao.
