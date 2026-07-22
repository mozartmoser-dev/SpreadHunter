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
        self.height_expanded = 270
        self.setFixedHeight(self.height_compact)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 6, 12, 6)
        self.main_layout.setSpacing(4)

        self.bar_compact = QWidget()
        layout_compact = QHBoxLayout(self.bar_compact)
        layout_compact.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QProgressBar

        self.lbl_summary = QLabel()
        self.lbl_summary.setProperty("class", "BadgeCompacto")
        layout_compact.addWidget(self.lbl_summary)
        layout_compact.addStretch()

        self.term_ibov = QProgressBar()
        self.term_ibov.setRange(0, 100)
        self.term_ibov.setValue(50)
        self.term_ibov.setFixedSize(80, 14)
        self.term_ibov.setFormat("IBOV")
        self.term_ibov.setStyleSheet("""
            QProgressBar {
                background-color: #2d2d2d; border: 1px solid #444;
                border-radius: 4px; text-align: center; color: #fff; font-size: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e74c3c, stop:0.5 #f1c40f, stop:1 #2ecc71);
                border-radius: 3px;
            }
        """)
        layout_compact.addWidget(self.term_ibov)

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
        self._atualizar_cotacoes()

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
        grid_br.setSpacing(3)
        for i, (ativo, peso, preco) in enumerate([
            ("VALE3", "13.76%", "R$ 75,54"), ("ITUB4", "8.42%", "R$ 42,90"),
            ("PETR4", "5.80%", "R$ 42,67"), ("BBDC4", "3.98%", "R$ 18,99"),
            ("SBSP3", "3.54%", "R$ 29,44"), ("BPAC11", "3.20%", "R$ 35,10"),
            ("WEGE3", "3.19%", "R$ 46,70"), ("B3SA3", "2.95%", "R$ 15,75"),
        ]):
            grid_br.addWidget(self._lbl(ativo, bold=True), i, 0)
            grid_br.addWidget(self._lbl(peso), i, 1)
            grid_br.addWidget(self._lbl(preco, cor="#2ed573"), i, 2)
        col_br.addLayout(grid_br)
        col_br.addStretch()

        col_fut = QVBoxLayout()
        col_fut.setSpacing(3)
        lbl_fut = QLabel("Futuros & DI (Vencimentos)")
        lbl_fut.setProperty("class", "TituloColuna")
        col_fut.addWidget(lbl_fut)
        grid_fut = QGridLayout()
        grid_fut.setSpacing(3)
        for i, (ativo, info, preco) in enumerate([
            ("WIN$ (Ago24)", "Mini Ibov", "178.775"),
            ("WDO$ (Ago24)", "Mini Dolar", "5.070"),
            ("DI1F27", "Jan/27", "13.95"),
            ("DI1F33", "Jan/33", "14.71"),
            ("IND$ (Ago24)", "Ibov Cheio", "177.547"),
            ("DOL$ (Ago24)", "Dolar Cheio", "5.068"),
        ]):
            grid_fut.addWidget(self._lbl(ativo, bold=True), i, 0)
            grid_fut.addWidget(self._lbl(info, cor="#a4b0be"), i, 1)
            grid_fut.addWidget(self._lbl(preco, cor="#fdcb6e"), i, 2)
        col_fut.addLayout(grid_fut)
        col_fut.addStretch()

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
        layout_expanded.addLayout(col_fut, stretch=1)
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
        partes = ["<b>CDI:</b> 14.25%"]
        defaults = {"WIN$": ("WIN", 178.775), "WDO$": ("WDO", 5.070), "IND$": ("IBOV", 177.547), "DI1$": ("DI1", 14.71)}
        if self._source and self._source.disponivel:
            try:
                for cod, (nome, fallback) in defaults.items():
                    dados = self._source.ler_campos(cod, "ask", "last") or {}
                    preco = dados.get("last") or dados.get("ask") or 0
                    if preco and preco > 0:
                        anterior = self._precos_anteriores.get(cod, preco)
                        var_pct = (preco - anterior) / anterior * 100 if anterior > 0 else 0
                        cor = "#2ecc71" if var_pct > 0 else "#e74c3c" if var_pct < 0 else "#dcdde1"
                        partes.append(f"<b>{nome}:</b> {preco:.2f} <span style='color:{cor};'>({var_pct:+.2f}%)</span>")
                        self._precos_anteriores[cod] = preco
                        if cod == "IND$":
                            self.term_ibov.setValue(int(min(max((preco - 170000) / 20000 * 100, 0), 100)))
                            self.term_ibov.setFormat(f"IBOV {preco:.0f}")
                    else:
                        partes.append(f"<b>{nome}:</b> {fallback:.3f}")
            except Exception:
                pass
        else:
            for cod, (nome, fallback) in defaults.items():
                partes.append(f"<b>{nome}:</b> {fallback:.3f}")
        partes.append("<b>Brent/Min:</b> 91.87 / 13.41 | <b>Vetor:</b> MISTO")

        vix_str = self._buscar_vix()
        if vix_str:
            partes.append(vix_str)

        self.lbl_summary.setText(" | ".join(partes))

    def _buscar_vix(self):
        try:
            import yfinance as yf
            t = yf.Ticker("^VIX")
            info = t.fast_info
            preco = getattr(info, 'last_price', None) or getattr(info, 'regular_market_previous_close', None)
            if preco and preco > 0:
                return f"<b>VIX:</b> {preco:.2f}"
        except Exception:
            pass
        return None

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
