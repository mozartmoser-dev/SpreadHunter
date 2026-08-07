# WhitelistBox4PDialog

Diálogo para gerenciar a whitelist de ativos monitorados no Box Spread 4 Pontas. Se a whitelist estiver vazia, todos os ativos são monitorados. Se preenchida, apenas os ativos listados aparecem no monitoramento Box 4P.

Persiste no banco como parâmetro `white_list_box4p` da estratégia `BOX_4P`.

## Contrato (Requisitos)

### `WhitelistBox4PDialog(db_path=None, parent=None) -> None`
**Garante:**
1. Tamanho mínimo 420×380.
2. Lista de ativos com seleção múltipla.
3. Campo de texto com placeholder "Código do ativo (ex: PETR4)".
4. Botões: Adicionar, Remover Selecionado(s), OK, Cancelar.

### `_adicionar() -> None`
**Garante:**
1. Converte para uppercase e faz trim.
2. Verifica duplicatas.
3. Adiciona à lista (não persiste ainda).

### `_remover() -> None`
**Garante:**
1. Remove itens selecionados da lista.

### `_confirmar() -> None`
**Garante:**
1. Coleta todos os itens, chama `salvar_whitelist()`.
2. `accept()` no diálogo.

## Funções de Módulo

### `ler_whitelist(db_path=None) -> list[str]`
**Garante:**
1. Lê parâmetro `white_list_box4p` do banco.
2. Se vazio/inexistente, retorna lista vazia.

### `salvar_whitelist(ativos, db_path=None) -> None`
**Garante:**
1. Ordena e deduplica ativos.
2. Salva via `ParametroRepository.save()`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog`, `QVBoxLayout`, `QHBoxLayout`, `QLabel`, `QPushButton`, `QListWidget`, `QLineEdit`, `QMessageBox`, `QAbstractItemView` | UI |
| `PySide6.QtCore` | `Qt` | Flags |
| `PySide6.QtGui` | `QFont` | Importado mas aparentemente não usado |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Persistência |
| `src.domain.entities.parametro_operacional` | `ParametroOperacional` | Entidade |
| `src.ui.desktop.theme` | `Palette` | Cores |

## Métricas

| Linhas | 167 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-06-16
- Estruturalmente idêntico a `BlacklistImportDialog` — ambos são CRUD de lista de ativos via `ParametroRepository`. Diferem apenas nas chaves, estratégia e textos.
- Whitelist vazia = "todos os ativos" (comportamento padrão inclusivo). Blacklist vazia = "nenhum excluído" (comportamento padrão permissivo).
- `QFont` é importado mas não usado — mesmo padrão do `BlacklistImportDialog`. Provável código compartilhado/duplicado.
