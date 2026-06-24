from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.patches as mpatches

from src.domain.services.pipeline_tracker import PipelineTracker

COR_FUNDO = "#1a1a2e"
COR_TEXTO = "#e0e0e0"
COR_MUTED = "#666"
COR_DESTAQUE = "#4fc3f7"
COR_BARRA_TOPO = "#2196f3"
COR_BARRA_FUNDO = "#0d47a1"
COR_REJEITADO = "#ef5350"


class _CanvasFunnel(FigureCanvasQTAgg):
    """Desenha funil clássico (trapézios centrados conectados)."""

    def __init__(self, tracker: PipelineTracker):
        n = len(tracker.stages)
        self.fig = Figure(figsize=(9, 0.55 * n + 1.2), dpi=110)
        self.fig.patch.set_facecolor(COR_FUNDO)
        super().__init__(self.fig)

        self._stages = tracker.stages
        self._max_ent = max((s.entrada for s in tracker.stages), default=1)

        self._ax = self.fig.add_axes([0.01, 0.01, 0.98, 0.98])
        self._ax.set_facecolor(COR_FUNDO)
        self._desenhar()
        self.mpl_connect("pick_event", self._on_pick)

    def _desenhar(self):
        ax = self._ax
        ax.clear()
        stages = self._stages
        n = len(stages)
        max_e = self._max_ent
        margem_x = max_e * 0.08

        ax.set_xlim(-margem_x, max_e + margem_x)
        ax.set_ylim(-0.6, n - 0.2)
        ax.invert_yaxis()
        ax.axis("off")

        y_top = 0.0
        y_bot = 0.0
        alt = 0.65

        for i, s in enumerate(stages):
            y_bot = i + alt
            w_top = s.entrada / max_e * max_e * 0.88
            w_bot = s.saida / max_e * max_e * 0.88
            w_min = max_e * 0.03
            w_top = max(w_top, w_min)
            w_bot = max(w_bot, w_min)
            cx = max_e / 2
            x0 = cx - w_top / 2
            x1 = cx - w_bot / 2

            ratio = 1.0 - (i / max(n - 1, 1)) * 0.45
            cor = self._rgb_tuplo(COR_BARRA_TOPO, ratio)
            cor_borda = self._rgb_tuplo("#1a3a5c", ratio)

            trap = mpatches.Polygon(
                [(x0, y_top), (x0 + w_top, y_top),
                 (x1 + w_bot, y_bot), (x1, y_bot)],
                closed=True, facecolor=cor, edgecolor=cor_borda,
                linewidth=0.8,
            )
            trap.set_picker(True)
            ax.add_patch(trap)

            # nome à esquerda
            ax.text(x0 - 6, (y_top + y_bot) / 2, s.nome,
                    va="center", ha="right", fontsize=7.5, color=COR_TEXTO,
                    fontfamily="sans-serif", fontweight="bold")

            # números dentro do trapézio
            rej = s.entrada - s.saida
            nums = f"{s.entrada}  →  {s.saida}"
            if rej > 0:
                nums += f"  (-{rej})"
            cor_num = "#fff" if w_top > max_e * 0.25 else COR_TEXTO
            ax.text(cx, (y_top + y_bot) / 2 + 0.06, nums,
                    va="center", ha="center", fontsize=7,
                    color=cor_num, fontfamily="Consolas", fontweight="bold")

            # motivo abaixo (se houver espaço)
            if s.motivo and i < 3:
                ax.text(cx, y_bot + 0.12, s.motivo[:80],
                        va="top", ha="center", fontsize=5.5,
                        color=COR_MUTED, fontfamily="sans-serif",
                        style="italic")

            # linha de conexão com próximo estágio
            if i < n - 1:
                s_prox = stages[i + 1]
                w_prox_top = s_prox.entrada / max_e * max_e * 0.88
                w_prox_top = max(w_prox_top, w_min)
                cx_prox = max_e / 2
                x0_prox = cx_prox - w_prox_top / 2
                cor_linha = self._rgb_tuplo("#2a4a7a", 0.6)
                ax.plot([x0 + w_top / 2, x0_prox + w_prox_top / 2],
                        [y_bot, y_bot + 0.08],
                        color=cor_linha, lw=0.6, zorder=0)
                ax.plot([x0, x0_prox], [y_bot, y_bot + 0.08],
                        color=cor_linha, lw=0.6, zorder=0)

            y_top = i + alt + 0.08

        # título interno
        ax.text(max_e / 2, -0.35, "Clique em cada estágio para detalhes",
                va="center", ha="center", fontsize=6.5,
                color=COR_MUTED, fontfamily="sans-serif")

    def _rgb_tuplo(self, hex_cor: str, ratio: float = 1.0) -> tuple:
        h = hex_cor.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        if ratio < 1.0:
            esc = 0.06
            r = esc + (r - esc) * ratio
            g = esc + (g - esc) * ratio
            b = esc + (b - esc) * ratio
        return (r, g, b)

    def _on_pick(self, event):
        artist = event.artist
        if not isinstance(artist, mpatches.Polygon):
            return
        cy = artist.get_xy()[:, 1].mean()
        idx = int(round(cy / 0.65))
        if 0 <= idx < len(self._stages):
            s = self._stages[idx]
            pct = s.rejeitados / max(s.entrada, 1) * 100
            lines = [
                f"<b style='color:{COR_DESTAQUE};font-size:10pt;'>{s.nome}</b>",
                f"<hr style='color:#334;'>",
                f"Entrada: <b>{s.entrada}</b> candidatos",
                f"Aprovados: <b>{s.saida}</b>",
                f"<span style='color:{COR_REJEITADO};'>Rejeitados: {s.rejeitados} ({pct:.0f}%)</span>",
            ]
            if s.motivo:
                lines.append(f"<hr style='color:#334;'>"
                             f"<span style='color:#aaa;'>Critério:</span><br>"
                             f"<span style='color:#e0e0e0;'>{s.motivo}</span>")
            self._mostrar_tooltip("\n".join(lines), event.mouseevent)

    def _mostrar_tooltip(self, html, mouseevent):
        if not hasattr(self, '_tooltip_label'):
            self._tooltip_label = QLabel(self)
            self._tooltip_label.setStyleSheet(
                "background: #0d0d1a; border: 1px solid #4fc3f7;"
                "border-radius: 6px; padding: 8px; font-size: 9pt;"
                "color: #e0e0e0;"
            )
            self._tooltip_label.setWordWrap(True)
            self._tooltip_label.setMaximumWidth(360)
            self._tooltip_label.hide()

        self._tooltip_label.setText(html)
        self._tooltip_label.adjustSize()
        mx = int(mouseevent.x)
        my = int(mouseevent.y)
        self._tooltip_label.move(mx + 15, my - 20)
        self._tooltip_label.raise_()
        self._tooltip_label.show()


class PipelineDialog(QDialog):
    def __init__(self, tracker: PipelineTracker | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Pipeline: {tracker.nome_estrategia if tracker else 'N/A'}")
        self.setMinimumWidth(880)
        self.setMinimumHeight(350)
        self.setStyleSheet(f"background-color: {COR_FUNDO}; color: {COR_TEXTO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        if not tracker or not tracker.stages:
            lbl = QLabel("Nenhum dado de pipeline disponível.\nExecute uma varredura primeiro.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {COR_MUTED}; font-size: 11pt; padding: 40px;")
            layout.addWidget(lbl)
            self.setMinimumHeight(120)
            return

        header = QLabel(
            f"<b style='color:{COR_DESTAQUE};font-size:11pt;'>{tracker.nome_estrategia}</b>"
            f"  —  <span style='color:#aaa;'>{tracker.total_entrada} candidatos → "
            f"{tracker.total_saida} viáveis</span>"
        )
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("padding: 6px; border-bottom: 1px solid #2d2d44;")
        layout.addWidget(header)

        canvas = _CanvasFunnel(tracker)
        layout.addWidget(canvas, stretch=1)

        btn_row = QVBoxLayout()
        btn_row.setSpacing(4)

        hint = QLabel("ESC/Ctrl+Shift+F fecha  |  Clique no funil para detalhes  |  Copiar")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {COR_MUTED}; font-size: 8pt;")
        btn_row.addWidget(hint)

        btn_copy = QPushButton("📋 Copiar texto")
        btn_copy.setFixedWidth(120)
        btn_copy.setStyleSheet(
            "QPushButton { background: #2d2d44; color: #e0e0e0; border: 1px solid #4fc3f7;"
            "border-radius: 4px; padding: 4px 12px; font-size: 9pt; }"
            "QPushButton:hover { background: #3d3d5e; }"
        )
        btn_copy.clicked.connect(lambda: self._copiar_texto(tracker))
        btn_row.addWidget(btn_copy, alignment=Qt.AlignCenter)

        layout.addLayout(btn_row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier and event.key() == Qt.Key_F:
            self.close()
        super().keyPressEvent(event)

    def _copiar_texto(self, tracker):
        linhas = [f"{tracker.nome_estrategia} — {tracker.total_entrada} candidatos → {tracker.total_saida} viáveis"]
        for s in tracker.stages:
            dif = s.entrada - s.saida
            motivo = f" — {s.motivo}" if s.motivo else ""
            linhas.append(f"{s.nome} | {s.entrada} → {s.saida} (-{dif}){motivo}")
        QGuiApplication.clipboard().setText("\n".join(linhas))
