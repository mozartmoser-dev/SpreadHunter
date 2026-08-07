# GradeOpcoesDialog

## Propósito

Diálogo visualizador da grade de opções estilo Profit Pro — calls à esquerda, strike ao centro, puts à direita, agrupado por série (vencimento). Permite filtrar por ativo e série. Botão "Atualizar" dispara importação de instrumentos via `importflash.main()` em thread separada (`_ImportThread`), com barra de progresso e captura de stdout/stderr em tempo real.

## Contrato (Requisitos)

### `carregar_dados()`
**Garante:**
1. Lê todos os instrumentos de `InstrumentoRepository.get_all()`.
2. Popula o combobox de ativos com valores únicos ordenados.
3. Chama `_repopular_serie()` para popular a grade do ativo selecionado.

### `_repopular_serie()`
**Garante:**
1. Filtra instrumentos pelo ativo selecionado no combobox.
2. Agrupa por vencimento (série).
3. Para cada série, identifica se é semanal (W1-W5) ou mensal.
4. Cria `QTreeWidgetItem` para cada série com filhos: calls (esquerda), strike central, puts (direita).
5. Detecta duplicatas (mesmo código em múltiplas séries — problema de importação) e alerta.
6. Exibe status: "X séries — Y opções".

### `_label_serie(venc, codigos)`
**Garante:**
1. Detecta sufixo semanal: regex `W([1-9])` no código.
2. Se a maioria dos códigos tem o mesmo sufixo W, retorna "SEMANA N — DD/MM/YYYY".
3. Caso contrário: "MENSAL — DD/MM/YYYY".

### `_atualizar_base()`
**Garante:**
1. Desabilita o botão "Atualizar".
2. Mostra progress bar indeterminada.
3. Inicia `_ImportThread` que executa `importflash.main()` com stdout/stderr capturados.
4. Ao finalizar: recarrega dados, notifica callback `_on_import_concluido` (se definido), reabilita botão.

### `_ImportThread`
**Garante:**
1. Roda em QThread separada (não QProcess — importante para PyInstaller, onde `sys.executable` falha).
2. Captura stdout/stderr linha a linha via `_LineCapture` (subclasse de `StringIO`).
3. Emite `progress.emit(line)` para cada linha de log.
4. Emite `finished.emit(rc)` com exit code do `importflash.main()`.
5. Em caso de exceção, captura traceback e emite `finished(1)`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `io` | stdlib | `StringIO` para captura de output |
| `contextlib` | stdlib | `redirect_stdout/stderr` |
| `math` | stdlib | (importado, uso não localizado) |
| `zoneinfo` | `ZoneInfo` | (importado, uso não localizado no trecho lido) |
| `re` | stdlib | Regex `W[1-9]` para detectar semanais |
| `datetime` | `date` | Datas |
| `PySide6.QtCore` | `Qt, QThread, Signal` | Thread e sinais |
| `PySide6.QtGui` | `QColor, QFont` | Estilo |
| `PySide6.QtWidgets` | `QAbstractItemView, QComboBox, QDialog, ..., QVBoxLayout` | UI framework |
| `src.domain.entities.instrumento_opcional` | `TipoOpcao` | Enum de tipo |
| `src.infrastructure.persistence.repositories.repositories` | `InstrumentoRepository` | Leitura de instrumentos |
| `src.ui.desktop.flag_icons` | `flag_icon` | Ícones de bandeira |
| `src.ui.desktop.theme` | `Palette` | Cores |

## Métricas

| Linhas | 426 |
| Classes | 2 (`_ImportThread`, `GradeOpcoesDialog`) |
| Testes | Não |

## Notas

- **Import em QThread (não QProcess):** Regra explícita do AGENTS.md — `sys.executable` falha no .exe PyInstaller. Usar QThread garante que o `importflash.main()` rode no mesmo processo.
- **`_LineCapture` como classe interna de `_ImportThread.run()`:** Definida dentro do método `run()`, não no escopo da classe — incomum, mas funcional.
- **`_on_import_concluido` callback:** Opcional, passado no construtor. Usado pela `MainWindow` para chamar `MonitorWorker.recarregar_instrumentos()` após a importação.
- **Detecção de duplicatas:** Se um mesmo código de opção aparece em múltiplas séries (ex: PETRH300 na série mensal e na W1), o diálogo alerta — isso indica que a base de instrumentos precisa ser limpa.
- **`_MESES_PT`:** Mapeamento de número do mês para sigla em português (JAN, FEV, ..., DEZ) — usado nos labels das séries.
