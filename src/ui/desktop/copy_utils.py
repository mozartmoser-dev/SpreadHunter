from io import BytesIO

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QTableView, QTextEdit


def copiar_texto_formatado(widget: QTextEdit) -> None:
    """Copia conteúdo do QTextEdit como HTML + plain text para o clipboard."""
    html = widget.toHtml()
    plain = widget.toPlainText()
    if not plain:
        return
    mime = QMimeData()
    mime.setHtml(html)
    mime.setText(plain)
    QGuiApplication.clipboard().setMimeData(mime)


def copiar_figura_clipboard(fig) -> None:
    """Renderiza matplotlib Figure para PNG e cola como imagem no clipboard."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    img = QImage()
    img.loadFromData(buf.read(), "PNG")
    QGuiApplication.clipboard().setImage(img)


def salvar_figura_arquivo(fig, parent=None) -> None:
    """Salva matplotlib Figure como PNG via diálogo."""
    path, _ = QFileDialog.getSaveFileName(
        parent, "Salvar gráfico como...", "", "PNG (*.png)")
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight",
                     facecolor=fig.get_facecolor())


def _valor_csv(r, chave: str, model=None, model_row: int | None = None,
               colunas: list[tuple[str, str]] | None = None):
    """Extrai o valor exibido pela grade (respeita a formatacao do modelo).

    Prioridades:
      1. ``model`` + ``model_row``: chama ``model.data(idx, DisplayRole)`` na
         coluna correspondente a ``chave``. Reproduz EXATAMENTE o que o
         usuario ve. ``colunas`` eh opcional como hint quando o model nao
         expoe COLUMNS como atributo.
      2. ``model`` sem ``model_row``: nao eh esperado.
      3. Fallback: getattr direto em ``r`` (``label_detectado`` sintetizado
         a partir de ``detectado_em`` quando faltar).
    """
    cols = colunas
    if cols is None and model is not None and hasattr(model, "COLUMNS"):
        cols = model.COLUMNS

    if model is not None and model_row is not None and cols is not None:
        from PySide6.QtCore import Qt
        for col_idx, (_, c_key) in enumerate(cols):
            if c_key == chave:
                idx = model.index(model_row, col_idx)
                rendered = model.data(idx, Qt.ItemDataRole.DisplayRole)

                # CSV mantem o codigo canonico (A/E) em vez de bandeirinhas.
                # Bandeirinhas sao puramente display (DecorationRole).
                if chave == "tipo_opcao":
                    v = getattr(r, chave, None)
                    return v if v else "-"

                return rendered  # mantem exatamente o que a grade mostra

    if "." in chave:
        obj, attr = chave.rsplit(".", 1)
        owner = getattr(r, obj, None)
        return getattr(owner, attr, None) if owner is not None else None

    if chave == "label_detectado" and not hasattr(r, "label_detectado"):
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo as _zi
        _d = getattr(r, "detectado_em", None)
        if isinstance(_d, _dt):
            if _d.tzinfo is None:
                _d = _d.replace(tzinfo=_zi("America/Sao_Paulo"))
            return _d.astimezone(_zi("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S (Brasília)")
        if _d is not None:
            return str(_d)
        return None

    return getattr(r, chave, None)


def exportar_monitor_csv(
    resultados: list,
    colunas: list[tuple[str, str]],
    table_view: QTableView | None = None,
    parent=None,
    titulo_janela: str = "Export CSV",
) -> int:
    """Exporta a grade do monitor para CSV via clipboard.

    - ``resultados``: lista de objetos (Resultado* / OportunidadeMonitor).
    - ``colunas``: lista de (header_visivel, atributo), mesmo padrao dos models.
      Tambem serve como hint quando o model nao expoe COLUMNS diretamente
      (caixa BOX 4P usa constante global).
    - ``table_view``: se informado e houver linhas selecionadas, exporta so elas.
    - Retorna a quantidade de linhas exportadas.
    """
    if not resultados:
        QMessageBox.information(parent, titulo_janela, "Nenhum resultado para exportar.")
        return 0

    model = None
    proxy = None
    if table_view is not None:
        proxy = table_view.model()
        if proxy is not None and hasattr(proxy, "mapToSource"):
            model = proxy.sourceModel()
        else:
            model = proxy

    selecionadas: list = []
    rows_escolhidas: list[int] = []
    if table_view is not None and proxy is not None:
        sel_model = table_view.selectionModel()
        if sel_model is not None:
            selection = sel_model.selection()
            indices = selection.indexes() if selection is not None else []
            # Apenas trata como "selecionada" se houver indices validos (>0).
            # Selecoes vazias (hasSelection=False) fazem fallback para todas.
            raw_rows = sorted({i.row() for i in indices if i.isValid()})
            if raw_rows:
                for row in raw_rows:
                    if hasattr(proxy, "mapToSource"):
                        src_idx = proxy.mapToSource(proxy.index(row, 0))
                        real_row = src_idx.row() if hasattr(src_idx, "row") else row
                    else:
                        real_row = row
                    if 0 <= real_row < len(resultados):
                        rows_escolhidas.append(real_row)
                        selecionadas.append(resultados[real_row])

    alvo = selecionadas if selecionadas else resultados
    rows_iter = rows_escolhidas if selecionadas else list(range(len(resultados)))
    modo = "selecionadas" if selecionadas else "todas"

    headers = [c[0] for c in colunas]
    chaves = [c[1] for c in colunas]

    import csv, io
    saida = io.StringIO()
    writer = csv.writer(saida, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for r, model_row in zip(alvo, rows_iter):
        linha = []
        for chave in chaves:
            v = _valor_csv(r, chave, model=model, model_row=model_row,
                           colunas=colunas)
            # CSV: cell vazia ou nula vira '-'. Mantem bandeirinhas A/E intactas
            # se cair no bloco caído (caso não haja model).
            if v is None or v == "":
                linha.append("-")
            else:
                linha.append(str(v))
        writer.writerow(linha)

    QApplication.clipboard().setText(saida.getvalue())
    QMessageBox.information(
        parent,
        titulo_janela,
        f"{len(alvo)} linha(s) ({modo}) exportada(s) para a area de transferencia.\n"
        "Cole (Ctrl+V) aqui no chat para conferencia.",
    )
    return len(alvo)
