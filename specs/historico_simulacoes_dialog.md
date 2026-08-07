# HistoricoSimulacoesDialog

## Propósito

Diálogo de visualização do histórico de simulações otimizadas (Collar Calendário). Lista registros persistidos pelo `MonitorWorker._processar_otimizado()` no `HistoricoSimulacoesRepository`. Exibe 17 colunas com dados das variantes otimizadas: chassi, estágio, strikes, DTE, IV, ratios, PnL nas caudas, breakevens, %CDI. Suporta exportação TSV e limpeza do histórico.

## Contrato (Requisitos)

### `_carregar()`
**Garante:**
1. Busca até 500 registros do `HistoricoSimulacoesRepository.listar(500)`.
2. Atualiza o modelo e o título da janela com a contagem.

### `_limpar()`
**Garante:**
1. Confirmação via `QMessageBox.question` (Yes/No).
2. Chama `self._repo.limpar()` — deleta todos os registros.
3. Recarrega a lista.

### `_exportar()`
**Garante:**
1. Gera TSV (tab-separated) com cabeçalho das 17 colunas.
2. Copia para clipboard para colar no Excel.

### `_on_row_double_clicked(index)`
**Garante:**
1. Exibe `QMessageBox.information` com todos os campos do registro selecionado.

### `HistoricoSimulacoesTableModel`
**Garante:**
1. 17 colunas com larguras predefinidas: ID (40), Chassi (80), Estágio (120), Ativo (70), Preço (80), Strike Call (80), Strike Put (80), DTE (50), IV Call (65), R. Call (60), R. Put (60), PnL Esq (80), PnL Dir (80), BE Esq (80), BE Dir (80), %CDI (70), Detectado (140).
2. Formatação: preços/strikes com 2 casas decimais, PnL com 4 casas, %CDI como percentual.
3. Alinhamento: centro para ID/Chassi/DTE/IV/Ratios, direita para valores numéricos, esquerda para texto.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `logging` | stdlib | Logging |
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView, QHeaderView, QMessageBox` | UI framework |
| `PySide6.QtCore` | `Qt, QAbstractTableModel, QTimer` | Modelo |
| `PySide6.QtGui` | `QFont` | Fonte |
| `src.infrastructure.persistence.database` | `get_db_path` | Path do banco |
| `src.infrastructure.persistence.repositories.repositories` | `HistoricoSimulacoesRepository` | Acesso a dados |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência |
| `src.ui.desktop.theme` | `Palette` | Cores |

## Métricas

| Linhas | 202 |
| Classes | 2 (`HistoricoSimulacoesTableModel`, `HistoricoSimulacoesDialog`) |
| Testes | Não |

## Notas

- **`COLUMNS` como lista de tuplas `(nome, largura)`:** Diferente dos outros modelos que usam `(nome, chave)`. A largura fixa é aplicada em `header.resizeSection(i, w)`.
- **Sem hash de otimização no modelo:** `atualizar` sempre chama `beginResetModel`/`endResetModel` — aceitável porque este diálogo é aberto sob demanda (não atualiza a cada 3s como as tabelas principais).
- **Limite de 500 registros:** `listar(500)` — fixo, sem paginação. Se houver mais de 500 simulações, as mais antigas não são exibidas.
- **Dados persistidos pelo `MonitorWorker`:** Cada variante otimizada (Base, Rendimento, Proteção, Platô, +Tail) é registrada no banco com ~50 campos. Este diálogo exibe apenas 17 colunas — resumo para análise rápida.
