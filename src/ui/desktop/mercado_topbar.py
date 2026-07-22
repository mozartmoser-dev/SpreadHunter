from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QGridLayout


class MercadoTopBarWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MercadoTopBar")
        self.setStyleSheet("""
            QFrame#MercadoTopBar {
                background-color: #121212;
                border: 1px solid #2d2d2d;
                border-bottom: 2px solid #0984e3;
                border-radius: 6px;
            }
            QLabel { color: #f1f2f6; font-family: 'Segoe UI', Arial, sans-serif; }
            .BadgeCompacto { color: #a4b0be; font-size: 11px; font-weight: 500; }
            .DestaquePositivo { color: #2ecc71; font-weight: bold; }
            .DestaqueAlivio { color: #00cec9; font-weight: bold; }
            .TituloColuna { color: #e1b12c; font-weight: bold; font-size: 11px; padding-bottom: 4px; border-bottom: 1px solid #2d2d2d; }
            .ItemTexto { color: #dfe4ea; font-size: 10.5px; }
        """)
        self.height_compact = 36
        self.height_expanded = 210
        self.setFixedHeight(self.height_compact)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 6, 12, 6)

        self.bar_compact = QWidget()
        layout_compact = QHBoxLayout(self.bar_compact)
        layout_compact.setContentsMargins(0, 0, 0, 0)
        self.lbl_summary = QLabel(
            "<b>CDI:</b> 14.25% | "
            "<b>WDO/WIN:</b> Dólar | "
            "<b>DI1F33:</b> 14.71 <span style='color:#00cec9;'>(Alívio)</span> | "
            "<b>Brent:</b> 91.87 | "
            "<b>Vetor:</b> MISTO"
        )
        self.lbl_summary.setProperty("class", "BadgeCompacto")
        layout_compact.addWidget(self.lbl_summary)
        layout_compact.addStretch()
        self.lbl_hint = QLabel("[Passe o mouse para expandir]")
        self.lbl_hint.setStyleSheet("color: #747d8c; font-size: 9.5px; font-style: italic;")
        layout_compact.addWidget(self.lbl_hint)
        self.main_layout.addWidget(self.bar_compact)

        self.panel_expanded = QWidget()
        layout_expanded = QHBoxLayout(self.panel_expanded)
        layout_expanded.setContentsMargins(0, 8, 0, 0)
        layout_expanded.setSpacing(15)

        col_br = QVBoxLayout()
        col_br.setSpacing(3)
        lbl_br = QLabel("Acoes BR (Pesos & Cotacoes)")
        lbl_br.setProperty("class", "TituloColuna")
        col_br.addWidget(lbl_br)
        grid_br = QGridLayout()
        grid_br.setSpacing(4)
        for i, (ativo, peso, preco) in enumerate([
            ("VALE3", "13.76%", "R$ 75,54"), ("ITUB4", "8.42%", "R$ 42,90"),
            ("PETR4", "5.80%", "R$ 42,67"), ("BBDC4", "3.98%", "R$ 18,99"),
        ]):
            grid_br.addWidget(self._lbl(ativo, bold=True), i, 0)
            grid_br.addWidget(self._lbl(peso), i, 1)
            grid_br.addWidget(self._lbl(preco, cor="#2ed573"), i, 2)
        col_br.addLayout(grid_br)
        col_br.addStretch()

        col_adr = QVBoxLayout()
        col_adr.setSpacing(3)
        lbl_adr = QLabel("ADRs (NYSE / Exterior)")
        lbl_adr.setProperty("class", "TituloColuna")
        col_adr.addWidget(lbl_adr)
        grid_adr = QGridLayout()
        grid_adr.setSpacing(4)
        for i, (ativo, preco) in enumerate([
            ("VALE", "$ 15.10"), ("ITUB", "$ 8.58"),
            ("PBR", "$ 15.20"), ("BBD", "$ 3.80"),
        ]):
            grid_adr.addWidget(self._lbl(ativo, bold=True), i, 0)
            grid_adr.addWidget(self._lbl(preco, cor="#2ed573"), i, 1)
        col_adr.addLayout(grid_adr)
        col_adr.addStretch()

        col_juros = QVBoxLayout()
        col_juros.setSpacing(3)
        lbl_juros = QLabel("Curva DI & Vertices (Estresse)")
        lbl_juros.setProperty("class", "TituloColuna")
        col_juros.addWidget(lbl_juros)
        grid_juros = QGridLayout()
        grid_juros.setSpacing(4)
        for i, (vertice, taxa, status) in enumerate([
            ("DI1F27", "13.95", "Fechamento Curva"),
            ("DI1F33", "14.71", "Alivio Pontual"),
            ("Inclinacao", "76 bps", "Achatamento (-)"),
        ]):
            grid_juros.addWidget(self._lbl(vertice, bold=True), i, 0)
            grid_juros.addWidget(self._lbl(taxa), i, 1)
            grid_juros.addWidget(self._lbl(status, cor="#00cec9"), i, 2)
        col_juros.addLayout(grid_juros)
        col_juros.addStretch()

        layout_expanded.addLayout(col_br, stretch=3)
        layout_expanded.addLayout(col_adr, stretch=2)
        layout_expanded.addLayout(col_juros, stretch=3)
        self.main_layout.addWidget(self.panel_expanded)
        self.panel_expanded.hide()

    def _lbl(self, texto, bold=False, cor=None):
        lbl = QLabel(texto)
        lbl.setProperty("class", "ItemTexto")
        style = ""
        if bold: style += "font-weight: bold; color: #ffffff;"
        if cor: style += f"color: {cor};"
        if style: lbl.setStyleSheet(style)
        return lbl

    def enterEvent(self, event):
        self.setFixedHeight(self.height_expanded)
        self.panel_expanded.show()
        self.lbl_hint.hide()

    def leaveEvent(self, event):
        self.setFixedHeight(self.height_compact)
        self.panel_expanded.hide()
        self.lbl_hint.show()
