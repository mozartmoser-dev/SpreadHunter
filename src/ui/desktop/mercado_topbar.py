from datetime import date
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QGridLayout


class MercadoTopBarWidget(QFrame):
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._source = None
        self._precos_anteriores: dict[str, float] = {}
        self.setObjectName("MercadoTopBar")
        self.setStyleSheet("""
            QFrame#MercadoTopBar {
                background-color: #121212;
                border: 1px solid #2d2d2d;
                border-bottom: 2px solid #0984e3;
                border-radius: 6px;
            }
            QLabel { color: #f1f2f6; font-family: 'Segoe UI', Arial, sans-serif; }
            .BadgeCompacto { color: #dcdde1; font-size: 10px; }
            .TickerLabel { color: #f39c12; font-size: 10.5px; font-weight: bold; }
            .TituloColuna { color: #e1b12c; font-weight: bold; font-size: 11px; padding-bottom: 4px; border-bottom: 1px solid #2d2d2d; }
            .ItemTexto { color: #dfe4ea; font-size: 10.5px; }
        """)
        self.height_compact = 58
        self.height_expanded = 240
        self.setFixedHeight(self.height_compact)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 6, 12, 6)
        self.main_layout.setSpacing(4)

        self.bar_compact = QWidget()
        layout_compact = QHBoxLayout(self.bar_compact)
        layout_compact.setContentsMargins(0, 0, 0, 0)
        self.lbl_summary = QLabel(
            "<b>CDI:</b> 14.25% | "
            "<b>IBOV:</b> 177.547 | "
            "<b>WIN:</b> 178.775 <span style='color:#fdcb6e;'>(+120p)</span> | "
            "<b>WDO:</b> 5.070 <span style='color:#fdcb6e;'>(-15p)</span> | "
            "<b>IVIX:</b> 21.40 pts | "
            "<b>DI1:</b> 14.71 | "
            "<b>Brent/Min:</b> 91.87 / 13.41 | "
            "<b>Vetor:</b> MISTO"
        )
        self.lbl_summary.setProperty("class", "BadgeCompacto")
        layout_compact.addWidget(self.lbl_summary)
        layout_compact.addStretch()
        self.lbl_hint = QLabel("[Hover para Acoes & ADRs]")
        self.lbl_hint.setStyleSheet("color: #747d8c; font-size: 9.5px; font-style: italic;")
        layout_compact.addWidget(self.lbl_hint)
        self.main_layout.addWidget(self.bar_compact)

        self.lbl_ticker = QLabel()
        self.lbl_ticker.setProperty("class", "TickerLabel")
        self.main_layout.addWidget(self.lbl_ticker)

        self.ticker_messages = []
        self.current_ticker_idx = 0
        self._carregar_eventos_do_dia()

        self.ticker_timer = QTimer(self)
        self.ticker_timer.timeout.connect(self.rotate_ticker)
        self.ticker_timer.start(4000)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._atualizar_cotacoes)
        self._refresh_timer.start(5000)

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
            ("SBSP3", "3.54%", "R$ 29,44"), ("WEGE3", "3.19%", "R$ 46,70"),
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

        layout_expanded.addLayout(col_br, stretch=1)
        layout_expanded.addLayout(col_adr, stretch=1)
        self.main_layout.addWidget(self.panel_expanded)
        self.panel_expanded.hide()

    def conectar_fonte(self, source):
        self._source = source
        if source and source.disponivel:
            for cod in ("WIN$", "WDO$", "IND$", "DOL$", "DI1$"):
                try:
                    source.registrar_topico(cod, "ask")
                    source.registrar_topico(cod, "last")
                except Exception:
                    pass

    def _atualizar_cotacoes(self):
        if not self._source or not self._source.disponivel:
            return
        partes = ["<b>CDI:</b> 14.25%"]
        try:
            for cod, nome in [("WIN$", "WIN"), ("WDO$", "WDO"), ("IND$", "IBOV"), ("DI1$", "DI1")]:
                dados = self._source.ler_campos(cod, "ask", "last") or {}
                preco = dados.get("last") or dados.get("ask") or 0
                if preco and preco > 0:
                    anterior = self._precos_anteriores.get(cod, preco)
                    var_pct = (preco - anterior) / anterior * 100 if anterior > 0 else 0
                    cor = "#2ecc71" if var_pct > 0 else "#e74c3c" if var_pct < 0 else "#dcdde1"
                    partes.append(f"<b>{nome}:</b> {preco:.2f} <span style='color:{cor};'>({var_pct:+.2f}%)</span>")
                    self._precos_anteriores[cod] = preco
        except Exception:
            pass
        self.lbl_summary.setText(" | ".join(partes))

    def _carregar_eventos_do_dia(self):
        hoje = date.today().isoformat()
        eventos = []
        try:
            from src.infrastructure.persistence.repositories.repositories import (
                DividendoRepository, CalendarioResultadosRepository,
            )
            repo_div = DividendoRepository(self.db_path)
            divs = repo_div.get_by_data_com(hoje)
            for d in divs:
                ativo = d.get("ativo", "?")
                valor = d.get("valor", 0)
                tipo = d.get("tipo", "Provento")
                eventos.append(f"[DATA COM HOJE]: {ativo} — R$ {valor:.4f} ({tipo})")

            repo_cal = CalendarioResultadosRepository(self.db_path)
            balancos = repo_cal.get_by_date_range(hoje, hoje)
            for b in balancos:
                ativo = b.get("ativo", "?")
                eventos.append(f"[BALANCO HOJE]: {ativo} — Divulgacao de Resultados")
        except Exception:
            pass

        if not eventos:
            eventos.append("[AGENDA]: Nenhum evento corporativo ou Data Com relevante para hoje.")

        self.ticker_messages = eventos
        self.current_ticker_idx = 0
        self.update_ticker_text()

    def update_ticker_text(self):
        if self.ticker_messages:
            self.lbl_ticker.setText(f"{self.ticker_messages[self.current_ticker_idx]}")

    def rotate_ticker(self):
        if self.ticker_messages:
            self.current_ticker_idx = (self.current_ticker_idx + 1) % len(self.ticker_messages)
            self.update_ticker_text()

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
