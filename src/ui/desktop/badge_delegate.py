from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QRectF


class BadgeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        model = index.model()
        col_key = model.COLUMNS[index.column()][1]
        text = index.data(Qt.ItemDataRole.DisplayRole)

        if not text or col_key not in ("label_tipo", "liq_indicator"):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Desenha o fundo da celula baseado no status da linha
        bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_brush:
            painter.fillRect(option.rect, bg_brush)
        else:
            # Alternancia de linhas padrao
            if option.features & option.Alternate:
                painter.fillRect(option.rect, QColor("#1e1e34"))
            else:
                painter.fillRect(option.rect, QColor("#1a1a2e"))

        # 2. Desenha destaque de selecao ou hover
        from PySide6.QtWidgets import QStyle
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2d4a7a"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#24243e"))

        # 3. Configura cores do Badge de acordo com o conteudo
        badge_bg = QColor(90, 90, 110, 20)
        badge_fg = QColor("#9090b0")
        display_text = text

        if col_key == "label_tipo":
            if "BOX+SBTH" in text:
                badge_bg = QColor(155, 89, 182, 35)  # Roxo semi-transparente
                badge_fg = QColor("#be8ee1")
            elif "BOX" in text:
                badge_bg = QColor(45, 74, 122, 50)  # Azul semi-transparente
                badge_fg = QColor("#7fb7ff")
            elif "SBTH" in text:
                badge_bg = QColor(26, 188, 156, 35)  # Ciano semi-transparente
                badge_fg = QColor("#1abc9c")
        elif col_key == "liq_indicator":
            if text in ("\u2713", "✓"):
                badge_bg = QColor(46, 204, 113, 35)  # Verde
                badge_fg = QColor("#2ecc71")
                display_text = "\u2713"
            elif text in ("\u2717", "✗"):
                badge_bg = QColor(231, 76, 60, 35)  # Vermelho
                badge_fg = QColor("#e74c3c")
                display_text = "\u2717"
            else:
                badge_bg = QColor(243, 156, 18, 35)  # Laranja
                badge_fg = QColor("#f39c12")
                display_text = "\u2713~"

        # 4. Desenha a pilula (pill) com cantos arredondados
        rect = QRectF(option.rect)
        
        # Limita a largura maxima da pilula para nao esticar demais em colunas largas
        max_width = 90 if col_key == "label_tipo" else 50
        pill_width = min(rect.width() - 16, max_width)
        pill_height = rect.height() - 8
        
        # Centraliza horizontal e verticalmente
        x = rect.x() + (rect.width() - pill_width) / 2
        y = rect.y() + (rect.height() - pill_height) / 2
        pill_rect = QRectF(x, y, pill_width, pill_height)

        painter.setBrush(QBrush(badge_bg))
        painter.setPen(QPen(badge_fg, 1))
        painter.drawRoundedRect(pill_rect, 4, 4)

        # 5. Desenha o texto do badge centralizado
        painter.setPen(badge_fg)
        font = painter.font()
        font.setBold(True)
        if col_key == "liq_indicator":
            font.setPointSize(10)
        else:
            font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, display_text)

        painter.restore()
