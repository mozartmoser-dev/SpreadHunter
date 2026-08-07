# copy_utils

Utilitários de clipboard e exportação para a UI. Fornece funções para copiar conteúdo formatado (HTML + plain text), figuras matplotlib e exportar grades de monitoramento para CSV via clipboard.

## Contrato (Requisitos)

### `copiar_texto_formatado(widget) -> None`
**Garante:**
1. Extrai HTML e plain text do `QTextEdit`.
2. Se vazio, retorna sem fazer nada.
3. Seta clipboard com `QMimeData` contendo ambos os formatos.

### `copiar_figura_clipboard(fig) -> None`
**Garante:**
1. Renderiza matplotlib `Figure` para PNG em buffer (dpi=150, bbox_inches='tight', facecolor da figura).
2. Carrega em `QImage` e seta no clipboard.

### `salvar_figura_arquivo(fig, parent=None) -> None`
**Garante:**
1. Abre diálogo "Salvar como..." com filtro PNG.
2. Se caminho escolhido, salva figura com dpi=150.

### `exportar_monitor_csv(resultados, colunas, table_view=None, parent=None, titulo_janela="Export CSV") -> int`
**Garante:**
1. Se `table_view` tem linhas selecionadas (com `selectionModel` e índices válidos > 0), exporta apenas as selecionadas. Caso contrário, exporta todas.
2. Extrai valores via `_valor_csv()` que prioriza: `model.data(idx, DisplayRole)` > `getattr` direto.
3. Para `tipo_opcao`, usa valor canonical (`A`/`E`) em vez do ícone de bandeirinha.
4. Para `label_detectado`, sintetiza de `detectado_em` se o atributo não existir.
5. Suporta notação com ponto (`obj.attr`) para campos aninhados.
6. Células vazias/nulas viram "-" no CSV.
7. CSV gerado com `csv.QUOTE_MINIMAL`, colado no clipboard.
8. Exibe `QMessageBox.information` com contagem de linhas.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `io` | `BytesIO` | Buffer para renderização de PNG |
| `PySide6.QtCore` | `QMimeData` | Clipboard com múltiplos formatos |
| `PySide6.QtGui` | `QGuiApplication`, `QImage` | Clipboard de imagem |
| `PySide6.QtWidgets` | `QApplication`, `QFileDialog`, `QMessageBox`, `QTableView`, `QTextEdit` | UI e clipboard |
| `csv` | — | Geração de CSV (import lazy) |
| `io` | `StringIO` | Buffer de string para CSV (import lazy) |
| `datetime` | `datetime` | Formatação de `detectado_em` (import lazy em `_valor_csv`) |

## Métricas

| Linhas | 170 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-07-29
- `_valor_csv` tem um fallback complexo: se não há model ou model_row, tenta `getattr(r, chave)`. Isso lida com o caso de exportação sem tabela visível (ex: chamada programática).
- O tratamento de `label_detectado` sintetiza de `detectado_em` com timezone Brasília hardcoded na string ("Brasília") — **POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão**: se `detectado_em` já for timezone-aware, a string fixa "Brasília" pode ser incorreta.
- A detecção de linhas selecionadas depende de `selectionModel().selection().indexes()` — se o proxy model mapear índices, o código usa `proxy.mapToSource()` para obter a linha real.
