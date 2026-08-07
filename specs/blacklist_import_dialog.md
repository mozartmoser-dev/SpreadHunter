# BlacklistImportDialog

Diálogo para gerenciar a blacklist de ativos excluídos da importação do `importflash.py`. Ativos na blacklist são removidos durante a importação sem preservação (regra #8 do AGENTS.md).

Persiste no banco como parâmetro `black_list_import` da estratégia `IMPORTACAO`.

## Contrato (Requisitos)

### `BlacklistImportDialog(db_path=None, parent=None) -> None`
**Garante:**
1. Tamanho mínimo 420×380.
2. Lista de ativos com seleção múltipla.
3. Campo de texto com placeholder "Código do ativo (ex: PETR4)".
4. Botões: Adicionar, Remover Selecionado(s), OK, Cancelar.

### `_adicionar() -> None`
**Garante:**
1. Converte para uppercase e faz trim.
2. Verifica duplicatas (case-insensitive).
3. Adiciona à lista (não persiste ainda).

### `_remover() -> None`
**Garante:**
1. Remove itens selecionados da lista (não persiste ainda).

### `_confirmar() -> None`
**Garante:**
1. Coleta todos os itens da lista, chama `salvar_blacklist()`.
2. `accept()` no diálogo.

## Funções de Módulo

### `ler_blacklist(db_path=None) -> list[str]`
**Garante:**
1. Lê parâmetro `black_list_import` do banco.
2. Se vazio ou inexistente, retorna lista vazia.
3. Retorna ativos em uppercase, sem duplicatas.

### `salvar_blacklist(ativos, db_path=None) -> None`
**Garante:**
1. Ordena e deduplica ativos.
2. Salva como string separada por vírgula via `ParametroRepository.save()`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog`, `QVBoxLayout`, `QHBoxLayout`, `QLabel`, `QPushButton`, `QListWidget`, `QLineEdit`, `QMessageBox`, `QAbstractItemView` | UI |
| `PySide6.QtCore` | `Qt` | Flags |
| `PySide6.QtGui` | `QFont` | Fonte (importado mas aparentemente não usado) |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Persistência |
| `src.domain.entities.parametro_operacional` | `ParametroOperacional` | Entidade |
| `src.ui.desktop.theme` | `Palette` | Cores |

## Métricas

| Linhas | 167 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-06-16
- A blacklist é removida na importação sem preservação (regra #8 do AGENTS.md). Isso significa que re-importações não "lembram" ativos previamente na blacklist — a blacklist é aplicada como filtro no momento da importação.
- `ler_blacklist` e `salvar_blacklist` são funções de módulo (não métodos da classe), permitindo uso sem instanciar o diálogo.
- `QFont` é importado mas aparentemente não usado — parece ser resquício de refatoração.
