from io import BytesIO

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QFileDialog, QTextEdit


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
