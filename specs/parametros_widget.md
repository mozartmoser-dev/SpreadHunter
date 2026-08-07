# ParametrosWidget

Widget central de configuração de parâmetros do SpreadHunter. Expõe TODOS os parâmetros operacionais agrupados por estratégia (Geral, Colar, Collar Calendário, Box, SBTH, MPP, etc.) em uma interface com sidebar + stack de páginas, leitura/escrita via `ParametroRepository` e exportação JSON para `config/parametros_default.json`.

A classe auxiliar `NoWheelSpinBox` bloqueia o evento de roda do mouse em `QDoubleSpinBox` para evitar mudanças acidentais ao rolar a tela.

## Contrato (Requisitos)

### `ParametrosWidget(db_path, parent) -> None`
**Garante:**
1. Instancia `ParametroRepository(db_path)` e popula `self._widgets` via `_build_param_row` para cada parâmetro de cada estratégia.
2. Carrega valores do banco via `_carregar()`, com fallback para `ParametroOperacional.PARAMETROS_DEFAULT`.
3. Sidebar ordenada por `_SIDEBAR_ORDER` (17 estratégias). `BOX_SINTETICO` está oculto — feature não ativa.

### `_salvar() -> None`
**Garante:**
1. Para cada widget em `self._widgets`, serializa o valor e chama `self.repo.save(param)`.
2. Chaves em `self._pct_chaves` são divididas por 100 antes de salvar (exibição em %, armazenamento decimal).
3. Ao final, chama `_exportar_json()` para persistir no disco.

### `_exportar_json() -> None`
**Garante:**
1. Lê todos os parâmetros do banco via `repo.list_all()`.
2. Grava em `config/parametros_default.json` (seed do banco) e backup em `backconfsh/configsh.json`.
3. Silencia exceções — falha de exportação não impede salvamento.

### `_carregar() -> None`
**Garante:**
1. Para cada widget registrado, lê `repo.get_by_chave(chave)`, com fallback para `PARAMETROS_DEFAULT`.
2. Trata tipos específicos: `QCheckBox` (bool), `QComboBox` (índice/data), `QLineEdit` (texto), `QSlider` (int), `QDoubleSpinBox` (float, com conversão % para chaves `_pct_chaves`).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `json` | — | Exportação do arquivo de configuração |
| `collections` | `OrderedDict` | Ordem de parâmetros (não usado ativamente no código visível) |
| `pathlib` | `Path` | Resolução de caminho para `config/` e `backconfsh/` |
| `PySide6.QtWidgets` | Vários | Widgets da UI: QWidget, QVBoxLayout, QFormLayout, QGroupBox, QDoubleSpinBox, QPushButton, QLabel, QScrollArea, QFrame, QCheckBox, QComboBox, QLineEdit, QMessageBox, QHBoxLayout, QSlider, QFileDialog, QListWidget, QListWidgetItem, QStackedWidget |
| `PySide6.QtCore` | `Qt`, `QSettings` | Alinhamento, persistência de seleção da sidebar |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Leitura/escrita de parâmetros no banco |
| `src.domain.entities.parametro_operacional` | `ParametroOperacional` | Entidade de parâmetro + `PARAMETROS_DEFAULT` |
| `src.ui.desktop.theme` | `Palette` | Cores do tema |
| `winsound` | — | Teste de som (beep) |

## Métricas

| Linhas | 1431 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-08-07
- `BOX_SINTETICO` está definido em `ESTRATEGIA_LABELS` e `ESTRATEGIA_COLORS` mas não aparece em `_SIDEBAR_ORDER` — feature de Pescaria Basket não ativa.
- A sidebar em `_build_sidebar` usa `QListWidgetItem` com emoji + label. O item armazena a chave da estratégia em `Qt.UserRole` e a cor em `Qt.UserRole + 1`.
- Parâmetros de som (`som_arquivo`, `som_volume` e variantes `_vendidas`/`_coberta`) têm tratamento especial com `QComboBox` (lista de arquivos `.wav` de `C:\Windows\Media`) e `QSlider` de volume.
- O widget `NoWheelSpinBox` existe para evitar que rolagem acidental mude valores numéricos. **Possível problema de acessibilidade:** usuários que dependem de scroll wheel não conseguem usar spin boxes.
- `_exportar_json` faz backup duplo: `config/parametros_default.json` + `backconfsh/configsh.json`. O propósito do backup duplicado não está documentado [motivo não documentado, confirmar com o autor].
- `sourceMapping`/`não-óbvia`: Os `_widgets` para som (`_som_arquivo_widget`, `_som_arquivo_vendidas_widget`, `_som_arquivo_coberta_widget`) são armazenados como atributos da instância (não no dict `_widgets`) porque o container `QWidget` que envolve o combo é registrado no dict, não o combo em si.
