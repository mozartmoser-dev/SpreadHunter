import calendar
from datetime import date, timedelta
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QGridLayout, QProgressBar, QSizePolicy
from src.domain.services.market_data_source import FieldName

_MC = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
       7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}

_MESES_BIMESTRAIS = [2, 4, 6, 8, 10, 12]
_NOME_MES = {2: "Fev", 4: "Abr", 6: "Jun", 8: "Ago", 10: "Out", 12: "Dez"}


def _cod_fut(prefixo: str, ano: int, mes: int) -> str:
    return f"{prefixo.lower()}{_MC[mes].lower()}{str(ano)[-2:]}"


def _contrato_bimestral_ativo(hoje: date) -> tuple[int, int]:
    for bm in _MESES_BIMESTRAIS:
        venc = _segunda_quarta(hoje.year, bm)
        if hoje <= venc:
            return (hoje.year, bm)
    return (hoje.year + 1, _MESES_BIMESTRAIS[0])


def _segunda_quarta(year: int, month: int) -> date:
    quartas = []
    for d in range(1, 32):
        try:
            if calendar.weekday(year, month, d) == calendar.WEDNESDAY:
                quartas.append(d)
        except ValueError:
            break
    return date(year, month, quartas[1])


def _formatar_data_completa(data_iso: str) -> str:
    if not data_iso:
        return ""
    data_clean = data_iso[:10]
    if "-" in data_clean:
        try:
            partes = data_clean.split("-")
            if len(partes) == 3:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except Exception:
            pass
    return data_iso


class TickerWidget(QWidget):
    """Letreiro digital com rolagem contínua da direita para a esquerda."""

    BG = QColor("#121212")
    COR_BALANCO = QColor("#f1c40f")
    COR_BALANCO_FADED = QColor("#8a7a20")
    COR_PROVENTO = QColor("#2ecc71")
    COR_PROVENTO_FADED = QColor("#1a7a3e")
    COR_AGENDA = QColor("#747d8c")
    SEPARADOR = "    ◆    "

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setMinimumWidth(100)
        self._itens: list[tuple[str, QColor]] = []
        self._offset = 0.0
        self._velocidade = 35.0
        self._font = QFont("Consolas", 11)
        self._font.setStyleHint(QFont.Monospace)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scroll)
        self._timer.start(35)
        self._largura_total = 0.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_eventos(self, itens: list[tuple[str, QColor]]):
        self._itens = itens
        self._offset = float(self.width())
        self._largura_total = self._medir_largura_total()
        self.update()

    def _medir_largura_total(self) -> float:
        if not self._itens:
            return 0.0
        fm = self.fontMetrics()
        total = 0.0
        for i, (texto, _) in enumerate(self._itens):
            total += fm.horizontalAdvance(texto) + 24
            if i < len(self._itens) - 1:
                total += fm.horizontalAdvance(self.SEPARADOR) + 12
        return total

    def _scroll(self):
        if not self._itens:
            return
        self._offset -= self._velocidade * 0.035
        if self._offset < -(self._largura_total + 20):
            self._offset = float(self.width())
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self.BG)
        if not self._itens:
            p.setPen(QPen(self.COR_AGENDA))
            p.setFont(self._font)
            p.drawText(self.rect(), Qt.AlignCenter, "—")
            p.end()
            return

        p.setFont(self._font)
        x = self._offset
        fm = self.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2

        for texto, cor in self._itens:
            largura_texto = fm.horizontalAdvance(texto)
            p.setPen(QPen(cor))
            p.drawText(QRectF(x, 0, largura_texto + 60, self.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, texto)
            x += largura_texto + 24

            if cor != self._itens[-1][1] or texto != self._itens[-1][0]:
                p.setPen(QPen(self.COR_AGENDA.darker(150)))
                separador_l = fm.horizontalAdvance(self.SEPARADOR)
                p.drawText(QRectF(x, 0, separador_l + 30, self.height()),
                           Qt.AlignVCenter | Qt.AlignLeft, self.SEPARADOR)
                x += separador_l + 12

            if x > self.width() + 200:
                break

        p.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._offset < 0 and abs(self._offset) > self._largura_total + 20:
            self._offset = float(self.width())


class MercadoTopBarWidget(QFrame):
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._source = None
        self._precos_anteriores: dict[str, float] = {}
        self._registrados: set[str] = set()
        self._ref_prices: dict[str, float] = {}
        self._ref_date: date | None = None
        self.setObjectName("MercadoTopBar")
        self.setStyleSheet("""
            QFrame#MercadoTopBar {
                background-color: #121212;
                border: 1px solid #2d2d2d;
                border-bottom: 2px solid #0984e3;
                border-radius: 6px;
            }
            QLabel { color: #f1f2f6; font-family: 'Segoe UI', Arial, sans-serif; }
            .BadgeCompacto { color: #dcdde1; font-size: 11pt; }
            .TickerLabel { color: #f39c12; font-size: 10.5px; font-weight: bold; }
            .TituloColuna { color: #e1b12c; font-weight: bold; font-size: 11px; padding-bottom: 4px; border-bottom: 1px solid #2d2d2d; }
            .ItemTexto { color: #dfe4ea; font-size: 10.5px; }
        """)
        self.height_compact = 70
        self.height_expanded = 282
        self.setFixedHeight(self.height_compact)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 6, 12, 6)
        self.main_layout.setSpacing(4)

        self.bar_compact = QWidget()
        layout_compact = QHBoxLayout(self.bar_compact)
        layout_compact.setContentsMargins(0, 0, 0, 0)

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

        self.lbl_hint = QLabel("[Duplo-clique para Ações & ADRs]")
        self.lbl_hint.setStyleSheet("color: #747d8c; font-size: 9.5px; font-style: italic;")
        layout_compact.addWidget(self.lbl_hint)
        self.main_layout.addWidget(self.bar_compact)

        self.ticker = TickerWidget()
        self.main_layout.addWidget(self.ticker)

        self._carregar_eventos_do_dia()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._atualizar_tudo)
        self._refresh_timer.start(5000)
        self._vix_cache = (0.0, 0.0)
        self._atualizar_tudo()

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
        hoje = date.today()
        a_fut, m_fut = _contrato_bimestral_ativo(hoje)
        suf  = f"{_NOME_MES[m_fut]}{str(a_fut)[-2:]}"
        for i, (ativo, info, preco) in enumerate([
            ("WIN$ (" + suf + ")", "Mini Ibov", "178.775"),
            ("WDO$ (" + suf + ")", "Mini Dolar", "5.070"),
            ("DI1F27", "Jan/27", "13.95"),
            ("DI1F33", "Jan/33", "14.71"),
            ("IND$ (" + suf + ")", "Ibov Cheio", "177.547"),
            ("DOL$ (" + suf + ")", "Dolar Cheio", "5.068"),
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
        if source:
            for cod in self._gerar_defaults():
                try:
                    source.registrar_topico(cod, FieldName.BID)
                    source.registrar_topico(cod, FieldName.ASK)
                    source.registrar_topico(cod, FieldName.LAST_PRICE)
                    source.registrar_topico(cod, FieldName.CLOSE)
                    source.registrar_topico(cod, FieldName.VARIATION)
                    source.registrar_topico(cod, FieldName.OPEN)
                    self._registrados.add(cod)
                except Exception:
                    pass

    @staticmethod
    def _seta(var: float) -> str:
        if var > 0.0001:
            return "\u25b2"
        if var < -0.0001:
            return "\u25bc"
        return ""

    @staticmethod
    def _cor_var(var: float) -> str:
        if var > 0.0001:
            return "#2ecc71"
        if var < -0.0001:
            return "#e74c3c"
        return "#dcdde1"

    def _fmt_variacao(self, nome: str, valor: float, anterior: float | None, fmt: str = ".2f",
                       suffix: str = "", variacao: bool = True, variacao_manual: float | None = None) -> str:
        if not variacao:
            return f"<b>{nome}:</b> {valor:{fmt}}{suffix}"
        if variacao_manual is not None:
            var = variacao_manual
        elif anterior is None:
            return f"<b>{nome}:</b> {valor:{fmt}}{suffix} —"
        else:
            var = (valor - anterior) / anterior if anterior > 0 else 0.0
        cor = self._cor_var(var)
        seta = self._seta(var)
        return f"<b>{nome}:</b> {valor:{fmt}}{suffix} <span style='color:{cor};'>{seta}{var:+.2f}%</span>"

    def _buscar_vix(self) -> tuple[float, float | None]:
        import time
        agora = time.time()
        if agora - self._vix_cache[1] < 60 and self._vix_cache[0] > 0:
            return self._vix_cache[0], getattr(self, '_vix_prev_close', None)
        try:
            import yfinance as yf
            t = yf.Ticker("^VIX")
            info = t.fast_info
            preco = getattr(info, 'last_price', None) or getattr(info, 'regular_market_price', None)
            prev_close = getattr(info, 'regular_market_previous_close', None) or getattr(info, 'previous_close', None)
            if preco and preco > 0:
                self._vix_cache = (preco, agora)
                self._vix_prev_close = float(prev_close) if prev_close and prev_close > 0 else None
                return preco, self._vix_prev_close
        except Exception:
            pass
        return (self._vix_cache[0], getattr(self, '_vix_prev_close', None)) if self._vix_cache[0] > 0 else (0.0, None)

    def _atualizar_tudo(self):
        self._atualizar_cotacoes()
        self._eventos_cycle = getattr(self, '_eventos_cycle', 0) + 1
        if self._eventos_cycle >= 60:  # a cada ~5 min
            self._eventos_cycle = 0
            self._carregar_eventos_do_dia()

    def _gerar_defaults(self) -> dict[str, tuple[str, float]]:
        hoje = date.today()
        a, m_contrato = _contrato_bimestral_ativo(hoje)
        return {
            _cod_fut("WIN", a, m_contrato): ("WIN", 0.0),
            _cod_fut("WDO", a, m_contrato): ("WDO", 0.0),
            "IBOV": ("IBOV", 0.0),
            "DI1F27": ("DI27", 0.0),
            "DI1F33": ("DI33", 0.0),
            "BRENT-CFD": ("Brent", 0.0),
            "SFI$": ("Min", 0.0),
        }

    def _resetar_ref_se_necessario(self):
        hoje = date.today()
        if self._ref_date != hoje:
            self._ref_prices.clear()
            self._ref_date = hoje

    def _atualizar_cotacoes(self):
        self._resetar_ref_se_necessario()
        partes = []
        cdi = self._ler_cdi()
        partes.append(self._fmt_variacao("CDI", cdi, None, fmt=".2f", suffix="%", variacao=False))

        defaults = self._gerar_defaults()
        if self._source and self._source.disponivel:
            for cod in defaults:
                if cod not in self._registrados:
                    try:
                        for f in (FieldName.BID, FieldName.ASK, FieldName.LAST_PRICE,
                                  FieldName.CLOSE, FieldName.VARIATION, FieldName.OPEN):
                            self._source.registrar_topico(cod, f)
                        self._registrados.add(cod)
                    except Exception:
                        pass
            try:
                for cod, (nome, _fallback) in defaults.items():
                    dados = self._source.ler_campos(
                        cod, FieldName.BID, FieldName.ASK, FieldName.LAST_PRICE,
                        FieldName.CLOSE, FieldName.VARIATION, FieldName.OPEN,
                        allow_stale=True
                    ) or {}
                    preco = dados.get(FieldName.LAST_PRICE) or dados.get(FieldName.ASK) or dados.get(FieldName.BID) or 0
                    if preco and preco > 0:
                        var_oficial = dados.get(FieldName.VARIATION)
                        close_oficial = dados.get(FieldName.CLOSE)

                        if var_oficial is not None and isinstance(var_oficial, (int, float)) and var_oficial != 0.0:
                            var = float(var_oficial)
                        elif close_oficial is not None and isinstance(close_oficial, (int, float)) and close_oficial > 0:
                            var = (preco - float(close_oficial)) / float(close_oficial) * 100.0
                        else:
                            open_price = dados.get(FieldName.OPEN)
                            if open_price is not None and isinstance(open_price, (int, float)) and open_price > 0:
                                var = (preco - open_price) / open_price * 100.0
                            else:
                                if cod not in self._ref_prices:
                                    self._ref_prices[cod] = preco
                                ref = self._ref_prices.get(cod, preco)
                                var = (preco - ref) / ref * 100 if ref > 0 else 0.0

                        partes.append(self._fmt_variacao(nome, preco, None, variacao_manual=var))
                        self._precos_anteriores[cod] = preco
                        if cod == "IBOV":
                            self.term_ibov.setValue(int(min(max((preco - 170000) / 20000 * 100, 0), 100)))
                            self.term_ibov.setFormat(f"IBOV {preco:.0f}")
                    else:
                        partes.append(f"<b>{nome}:</b> —")
            except Exception:
                pass
        else:
            for cod, (nome, _fallback) in defaults.items():
                partes.append(f"<b>{nome}:</b> —")

        partes.append("<b>Vetor:</b> MISTO")

        vix_val, vix_prev = self._buscar_vix()
        if vix_val > 0:
            if vix_prev and vix_prev > 0:
                var = (vix_val - vix_prev) / vix_prev * 100.0
            else:
                if "VIX" not in self._ref_prices:
                    self._ref_prices["VIX"] = vix_val
                ref = self._ref_prices.get("VIX", vix_val)
                var = (vix_val - ref) / ref * 100 if ref > 0 else 0.0
            partes.append(self._fmt_variacao("VIX", vix_val, None, variacao_manual=var))
            self._precos_anteriores["VIX"] = vix_val
        else:
            partes.append("<b>VIX:</b> --")

        self.lbl_summary.setText(" | ".join(partes))

    def _ler_cdi(self) -> float:
        try:
            from src.infrastructure.persistence.repositories.repositories import ParametroRepository
            repo = ParametroRepository(self.db_path)
            p = repo.get_by_chave("taxa_cdi")
            if p and p.valor:
                return float(p.valor) * 100.0
        except Exception:
            pass
        return 14.25

    def _carregar_eventos_do_dia(self):
        hoje = date.today()
        hoje_iso = hoje.isoformat()
        itens: list[tuple[str, QColor]] = []
        try:
            from src.infrastructure.persistence.repositories.repositories import (
                DividendoRepository, CalendarioResultadosRepository,
            )
            repo_div = DividendoRepository(self.db_path)
            divs = repo_div.get_proximos(dias=1, dias_antes=1)
            for d in divs:
                ativo = d.get("ativo", "?")
                valor = d.get("valor", 0)
                tipo = d.get("tipo", "Provento")
                data_com = d.get("data_com", "")
                data_com_fmt = _formatar_data_completa(data_com)
                cor = TickerWidget.COR_PROVENTO if data_com == hoje_iso else TickerWidget.COR_PROVENTO_FADED
                itens.append((f"[{ativo}] {tipo}: R$ {valor:.4f} | COM: {data_com_fmt}", cor))

            repo_cal = CalendarioResultadosRepository(self.db_path)
            balancos = repo_cal.get_proximos(dias=1, dias_antes=1)
            for b in balancos:
                ativo = b.get("ativo", "?")
                data_pub = b.get("data_publicacao", "")
                data_pub_fmt = _formatar_data_completa(data_pub)
                tri = b.get("trimestre_referencia", "")
                cor = TickerWidget.COR_BALANCO if data_pub == hoje_iso else TickerWidget.COR_BALANCO_FADED
                itens.append((f"[{ativo}] Balanco {tri}: {data_pub_fmt}", cor))
        except Exception:
            pass

        if not itens:
            itens.append((f"[AGENDA] Nenhum evento corporativo ou Data Com para ontem/hoje/amanha.", TickerWidget.COR_AGENDA))

        self.ticker.set_eventos(itens)

    def _lbl(self, texto, bold=False, cor=None):
        lbl = QLabel(texto)
        lbl.setProperty("class", "ItemTexto")
        style = ""
        if bold: style += "font-weight: bold; color: #ffffff;"
        if cor: style += f"color: {cor};"
        if style: lbl.setStyleSheet(style)
        return lbl

    def _toggle(self):
        if self.panel_expanded.isVisible():
            self.setFixedHeight(self.height_compact)
            self.panel_expanded.hide()
            self.lbl_hint.show()
        else:
            self.setFixedHeight(self.height_expanded)
            self.panel_expanded.show()
            self.lbl_hint.hide()

    def mouseDoubleClickEvent(self, event):
        self._toggle()
