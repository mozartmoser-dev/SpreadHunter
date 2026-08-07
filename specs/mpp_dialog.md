# MppDialog

## Propósito

Diálogo do Motor de Priorização de Pescaria (MPP). Exibe ranking de boxes ordenados por score final com splitter vertical: tabela de ranking (topo) + painel de detalhes da oportunidade selecionada (base). Botão "Ativar MPP" persiste o estado no banco de dados (`mpp_habilitado`). Suporta alerta sonoro quando novos boxes aparecem.

## Contrato (Requisitos)

### `_setup_ui()`
**Garante:**
1. Header com label "Ranking de Pescaria" + indicador de status MPP (🔴 Desligado / 🟢 Ligado).
2. Botão sino (🔔) com toggle para alerta sonoro.
3. QSplitter vertical: `QTableView` (topo) + `QTextEdit` readonly (base) para detalhes.
4. Tabela com `MppTableModel`, sem ordenação habilitada (`setSortingEnabled(False)`) — ordenação é do modelo.
5. Botão "🟢 Ativar MPP" que alterna para "🔴 Desativar MPP" — persiste no banco via `ParametroRepository`.
6. Botão "📋 Regras" (oculto por default — `setVisible(False)`).
7. Botão "Fechar".

### `atualizar(boxes: list, mres: list)`
**Garante:**
1. Delega para `self._model.atualizar(boxes, mres)`.
2. Se som ativado e há boxes, toca alerta via `som_service.tocar(db_path)`.

### `_toggle_mpp(checked)`
**Garante:**
1. Atualiza parâmetro `mpp_habilitado` no banco (1 = ligado, 0 = desligado).
2. Atualiza label de status.
3. Emite `self.toggle_mpp_signal.emit(checked)` para o `MonitorWorker`.

### `_on_selecao()`
**Garante:**
1. Ao selecionar linha na tabela, popula o QTextEdit de detalhes com informações do box + MRE.
2. Exibe: ativo, box (K1×K2), score, nível, isca, IP, lote sugerido, confiança, persistência, spread médio, profundidade mínima, estado das 4 pernas.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableView, QHeaderView, QAbstractItemView, QTextEdit, QSplitter` | UI framework |
| `PySide6.QtCore` | `Qt, QTimer` | Timer para column utils |
| `PySide6.QtGui` | `QFont` | Fonte Consolas |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência |
| `src.ui.desktop.mpp_table_model` | `MppTableModel` | Modelo da tabela |
| `src.ui.desktop.theme` | `Palette` | Paleta de cores |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Persistir estado MPP |
| `src.domain.entities.parametro_operacional` | `ParametroOperacional` | (importado, uso via repositório) |

## Métricas

| Linhas | 322 |
| Classes | 1 |
| Testes | Não |

## Notas

- **`ParametroOperacional` importado mas uso não direto** — usado indiretamente via `ParametroRepository`. [motivo não documentado, confirmar com o autor].
- **`_setup_style()` inline no construtor:** Diferente de outros diálogos que usam `_setup_style()`, o MppDialog aplica stylesheet diretamente no `setStyleSheet` do construtor.
- **Tabela sem ordenação:** `setSortingEnabled(False)` — o modelo já entrega os dados ordenados por score. Ordenação manual pelo usuário não é suportada.
- **Som:** Toca via `src.infrastructure.services.som_service.tocar(db_path)` quando novos boxes viáveis aparecem (se sino ativado).
- **Botão "Regras" oculto:** `self.btn_regras.setVisible(False)` — funcionalidade planejada mas não implementada.
