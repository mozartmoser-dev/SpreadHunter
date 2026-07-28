from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget, QToolTip,
)
from PySide6.QtCore import Qt, QRectF, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QLinearGradient, QGuiApplication

from src.domain.services.pipeline_tracker import PipelineTracker

# ── Palette Bloomberg ──
_BG = "#0d0d1a"
_BG_ALT = "#12122a"
_HDR_BG = "#16213e"
_HDR_FG = "#ffd740"
_TEXT = "#e0e0e0"
_MUTED = "#888"
_GREEN = "#40c040"
_RED = "#ef5350"
_BORDER = "#2d2d44"
_BAR = "#4fc3f7"
_HEADERS = ["ESTÁGIO", "TOTAL", "APROVADOS", "REJEITADOS", "%", "PROGRESSO", "DURAÇÃO"]
_COL_WIDTHS = [200, 90, 105, 115, 70, 120, 80]


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _fmt_tempo(segundos: float) -> str:
    if segundos < 0.001:
        return f"{segundos*1000:.0f}µs"
    if segundos < 1.0:
        return f"{segundos*1000:.0f}ms"
    return f"{segundos:.2f}s"


def _mkitem(text: str, align: int = Qt.AlignCenter, color: str | None = None,
            bold: bool = False, size: int = 9) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(align | Qt.AlignVCenter)
    f = QFont("Consolas", size, QFont.Bold if bold else QFont.Normal)
    item.setFont(f)
    if color:
        item.setForeground(QColor(color))
    return item


class _BarWidget(QWidget):
    """Barra de progresso horizontal para a coluna PROGRESSO."""

    def __init__(self, pct: float, parent=None):
        super().__init__(parent)
        self._pct = min(pct, 1.0)
        self.setFixedSize(110, 18)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(QPen(QColor(_BORDER), 1))
        p.setBrush(QColor("#1a1a2e"))
        p.drawRoundedRect(QRectF(0, 1, w, h - 2), 3, 3)

        bw = max(6, int((w - 4) * self._pct))
        grad = QLinearGradient(0, 0, bw, 0)
        grad.setColorAt(0, QColor(_BAR))
        grad.setColorAt(1, QColor(_BAR).lighter(130))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(2, 3, bw, h - 6), 2, 2)
        p.end()


class PipelineDialog(QDialog):
    """Diálogo de pipeline estilo Bloomberg (tabela horizontal com barras)."""

    def __init__(self, tracker: PipelineTracker | None, parent=None):
        super().__init__(parent)
        self._tracker = tracker
        title = f"Pipeline: {tracker.nome_estrategia}" if tracker else "Pipeline: N/A"
        self.setWindowTitle(title)
        self.setMinimumWidth(820)
        self.setMinimumHeight(320)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {_BG}; color: {_TEXT}; }}
            QToolTip {{
                background-color: #0d0d1a;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: Consolas;
                font-size: 9pt;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        if not tracker or not tracker.stages:
            lbl = QLabel("Nenhum dado de pipeline disponível.\nExecute uma varredura primeiro.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {_MUTED}; font-size: 11pt; padding: 40px;")
            layout.addWidget(lbl)
            self.setMinimumHeight(120)
            return

        # ── Screen Header ──
        hdr = QLabel(f"SCREEN: PIPELINE {tracker.nome_estrategia}")
        hdr.setStyleSheet(f"color: {_HDR_FG}; font-size: 11pt; font-weight: bold; font-family: Consolas; padding: 2px 0;")
        layout.addWidget(hdr)

        # ── Tabela ──
        table = QTableWidget()
        table.setRowCount(len(tracker.stages))
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(_HEADERS)
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {_BG};
                alternate-background-color: {_BG_ALT};
                color: {_TEXT};
                font-family: Consolas; font-size: 9pt;
                border: 1px solid {_BORDER};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {_BORDER};
            }}
            QHeaderView::section {{
                background-color: {_HDR_BG};
                color: {_HDR_FG};
                font-weight: bold; font-size: 8pt; font-family: Consolas;
                padding: 4px 8px;
                border: none;
                border-bottom: 2px solid {_HDR_FG};
            }}
        """)
        table.cellClicked.connect(self._on_cell_clicked)

        max_val = max((s.entrada for s in tracker.stages), default=1)
        for i, s in enumerate(tracker.stages):
            pct_estagio = s.saida / s.entrada if s.entrada > 0 else 0
            pct_geral = s.saida / max_val if max_val > 0 else 0
            rej = s.entrada - s.saida

            table.setItem(i, 0, _mkitem(s.nome, Qt.AlignLeft | Qt.AlignVCenter))
            table.setItem(i, 1, _mkitem(_fmt(s.entrada)))
            table.setItem(i, 2, _mkitem(_fmt(s.saida), color=_GREEN))
            table.setItem(i, 3, _mkitem(_fmt(rej), color=_RED if rej > 0 else _MUTED))
            table.setItem(i, 4, _mkitem(f"{pct_estagio*100:.1f}%", color=_TEXT, bold=True))
            table.setCellWidget(i, 5, _BarWidget(pct_geral))
            table.setItem(i, 6, _mkitem(_fmt_tempo(s.tempo_s), color=_MUTED))

        for col, w in enumerate(_COL_WIDTHS):
            table.setColumnWidth(col, w)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)

        layout.addWidget(table, stretch=1)

        # ── Footer ──
        total_in = tracker.total_entrada
        total_out = tracker.total_saida
        pct_final = total_out / total_in * 100 if total_in > 0 else 0
        footer = QLabel(
            f"<span style='color:{_HDR_FG};font-weight:bold;font-size:10pt;'>VIÁVEIS: "
            f"<span style='color:#fff;'>{_fmt(total_out)}</span></span>"
            f"<span style='color:{_MUTED};font-size:9pt;'>  |  "
            f"APROVAÇÃO: <span style='color:{_GREEN};'>{pct_final:.1f}%</span></span>"
        )
        footer.setTextFormat(Qt.RichText)
        footer.setStyleSheet(f"padding: 4px 0; border-top: 1px solid {_BORDER};")
        layout.addWidget(footer)

        # ── Hint + Copy ──
        hint = QLabel("ESC fecha  |  Clique na linha para detalhes  |  Copiar")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {_MUTED}; font-size: 8pt;")
        layout.addWidget(hint)

        btn_copy = QPushButton("📋 Copiar texto")
        btn_copy.setFixedWidth(120)
        btn_copy.setStyleSheet(
            "QPushButton { background: #2d2d44; color: #e0e0e0; border: 1px solid #4fc3f7;"
            "border-radius: 4px; padding: 4px 12px; font-size: 9pt; }"
            "QPushButton:hover { background: #3d3d5e; }"
        )
        btn_copy.clicked.connect(lambda: self._copiar_texto(tracker))
        layout.addWidget(btn_copy, alignment=Qt.AlignCenter)

    # ── Events ──

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier and event.key() == Qt.Key_F:
            self.close()
        super().keyPressEvent(event)

    def _on_cell_clicked(self, row: int, _col: int):
        if not self._tracker or row >= len(self._tracker.stages):
            return
        s = self._tracker.stages[row]
        pct_rej = s.rejeitados / max(s.entrada, 1) * 100
        lines = [
            f"<b style='color:#4fc3f7;font-size:10pt;'>{s.nome}</b>",
            f"<hr style='border-color:#334;'>",
            f"Entrada: <b style='color:#e0e0e0;'>{_fmt(s.entrada)}</b> candidatos",
            f"Aprovados: <b style='color:#40c040;'>{_fmt(s.saida)}</b>",
            f"<span style='color:#ef5350;'>Rejeitados: {_fmt(s.rejeitados)} ({pct_rej:.0f}%)</span>",
            f"Tempo: <span style='color:#4fc3f7;'>{_fmt_tempo(s.tempo_s)}</span>",
        ]
        if s.motivo:
            lines.append(f"<hr style='border-color:#334;'>"
                         f"<span style='color:#aaa;'>Critério:</span><br>"
                         f"<span style='color:#e0e0e0;'>{s.motivo}</span>")
        html = ("<div style='background-color:#0d0d1a; color:#e0e0e0; padding:8px 12px; "
                "border:1px solid #2d2d44; border-radius:6px; font-family:Consolas; font-size:9pt;'>"
                + "<br>".join(lines)
                + "</div>")
        QToolTip.showText(QPoint(self.mapToGlobal(self.pos()).x() + 40,
                                 self.mapToGlobal(self.pos()).y() + 100),
                          html)

    def _copiar_texto(self, tracker):
        linhas = [
            f"{tracker.nome_estrategia} — {_fmt(tracker.total_entrada)} candidatos → "
            f"{_fmt(tracker.total_saida)} viáveis"
        ]
        for s in tracker.stages:
            dif = s.entrada - s.saida
            motivo = f" — {s.motivo}" if s.motivo else ""
            linhas.append(f"{s.nome} | {_fmt(s.entrada)} → {_fmt(s.saida)} (-{_fmt(dif)}) [{_fmt_tempo(s.tempo_s)}]{motivo}")
        QGuiApplication.clipboard().setText("\n".join(linhas))
