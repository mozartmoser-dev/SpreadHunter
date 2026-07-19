from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.domain.services.analise_mercado import MarketAnalyzer
from src.domain.services.calendario_b3 import B3_CALENDAR
from src.domain.services.market_data_source import FieldName
from src.infrastructure.integrations.ibov_composition_client import (
    IbovCompositionClient,
)
from src.infrastructure.persistence.database import get_db_path, get_connection
from src.infrastructure.persistence.repositories.repositories import (
    ParametroRepository,
    _parse_date,
)


_MESES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
          7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
_MC = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
       7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
_MC_INV = {v: k for k, v in _MC.items()}

_WEEKLY_CHARS = {"A", "B", "C", "D", "M", "N", "O", "P"}

FUTUROS: list[tuple[str, str]] = [
    ("WIN", "WIN"),
    ("WDO", "WDO"),
]

FUTUROS_FIXOS: list[tuple[str, str, date]] = [
    ("DI1F27", "DI1F27", date(2027, 1, 1)),
    ("DI1F33", "DI1F33", date(2033, 1, 1)),
]

FUTUROS_NOMINAIS: list[tuple[str, str]] = [
    ("BRENT-CFD", "BRENT-CFD"),
    ("EWZS-FMV", "EWZS-FMV"),
]


def _is_weekly(cod: str) -> bool:
    if len(cod) < 5:
        return False
    return cod[4].upper() in _WEEKLY_CHARS


def _limpar_nome_ativo(nome: str) -> str:
    if not nome:
        return ""
    nome = nome.replace("DI1 Jan/27", "DI1F27").replace("DI1 Jan/2", "DI1F27")
    nome = nome.replace("DI1 Jan/33", "DI1F33").replace("DI1 Jan/3", "DI1F33")
    return nome


def _cod(prefixo: str, ano: int, mes: int) -> str:
    return f"{prefixo.lower()}{_MC[mes].lower()}{str(ano)[-2:]}"


def _prox_mes(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _venc_win(mes: int, ano: int) -> date:
    d = date(ano, mes, 15)
    off = (2 - d.weekday()) % 7
    if off > 3:
        off -= 7
    return d + timedelta(days=off)


def _venc_wdo(mes: int, ano: int) -> date:
    d = date(ano, mes, 1)
    while True:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue
        try:
            if np.busday_count(date(ano, mes, 1), d + timedelta(days=1), busdaycal=B3_CALENDAR) > 0:
                break
        except Exception:
            if d.weekday() < 5:
                break
        d += timedelta(days=1)
    return d


def _venc_di(mes: int, ano: int) -> date:
    d = date(ano, mes, 1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _venc_futuro(cod: str) -> date:
    mes = _MC_INV.get(cod[3].upper(), 1)
    ano = 2000 + int(cod[4:6])
    p = cod[:3].upper()
    if p == "WIN":
        return _venc_win(mes, ano)
    if p == "WDO":
        return _venc_wdo(mes, ano)
    if p == "DI1" or p == "DI":
        return _venc_di(mes, ano)
    return date(ano, mes, 1)


class SensibilidadeMercadoWidget(QWidget):
    def __init__(self, db_path: str | None = None, source=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._db_path = db_path or get_db_path()
        self._openfast = source
        self._ref_prices: dict[str, float] = {}
        self._ref_settled: set[str] = set()
        self._rows_fut: list[dict] = []
        self._rows_ibov: list[dict] = []
        self._taxa_cdi = 0.1425
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar)
        self._primeira_poll_feita = False
        self._ibov_client = IbovCompositionClient()
        self._compass_pixmap: QPixmap | None = None

        self._setup_ui()
        self._inicializar()
        self._timer.start(3000)

    def _setup_ui(self):
        self.setWindowTitle("Sensibilidade de Mercado")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(620, 360)
        self.resize(720, 520)

        self.setStyleSheet("""
            SensibilidadeMercadoWidget {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #14142a, stop:1 #0e0e1a);
            }
        """)

        l = QVBoxLayout(self)
        l.setContentsMargins(6, 2, 6, 8)
        l.setSpacing(4)

        # Status indicator (inline with title via window)
        self._lbl_status = QLabel()
        self._lbl_status.setFixedSize(10, 10)
        self._lbl_status.setStyleSheet("background:#f39c12;border-radius:5px;")

        # CDI
        cdi_row = QHBoxLayout()
        cdi_row.setSpacing(6)
        self._lbl_cdi = QLabel()
        self._lbl_cdi.setFont(QFont("Consolas", 10))
        self._lbl_cdi.setStyleSheet("color:#0ff;background:transparent;")
        cdi_row.addWidget(self._lbl_cdi)
        cdi_row.addWidget(self._lbl_status)
        cdi_row.addStretch()
        l.addLayout(cdi_row)

        # Curva DI + Vetor (analysis header)
        self._lbl_curva = QLabel()
        self._lbl_curva.setFont(QFont("Consolas", 10, QFont.Bold))
        self._lbl_curva.setStyleSheet("color:#ccc;background:transparent;")
        l.addWidget(self._lbl_curva)

        self._lbl_vetor = QLabel()
        self._lbl_vetor.setFont(QFont("Consolas", 9))
        self._lbl_vetor.setStyleSheet("color:#ccc;background:transparent;")
        l.addWidget(self._lbl_vetor)

        # Separator
        s = QFrame()
        s.setFrameShape(QFrame.HLine)
        s.setStyleSheet("color:#2d2d44;")
        l.addWidget(s)

        # Two-column scroll area
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setStyleSheet(
            "QScrollArea{background:transparent;}"
            "QScrollBar:vertical{width:6px;background:#1a1a30;}"
            "QScrollBar::handle:vertical{background:#3d3d55;border-radius:3px;}"
        )
        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background:transparent;")
        self._two_cols = QHBoxLayout(self._scroll_content)
        self._two_cols.setContentsMargins(0, 0, 0, 0)
        self._two_cols.setSpacing(16)

        # Column 0: Futures
        self._col0 = QVBoxLayout()
        self._col0.setSpacing(2)
        lbl_fut = QLabel("FUTUROS")
        lbl_fut.setFont(QFont("Consolas", 9, QFont.Bold))
        lbl_fut.setStyleSheet("color:#f0c040;background:transparent;")
        self._col0.addWidget(lbl_fut)
        h0 = QHBoxLayout()
        h0.setSpacing(6)
        for txt, w, align in [("Ativo", 70, Qt.AlignmentFlag.AlignLeft),
                              ("Venc", 70, Qt.AlignmentFlag.AlignLeft),
                              ("Últ", 90, Qt.AlignmentFlag.AlignRight),
                              ("Var%", 70, Qt.AlignmentFlag.AlignRight)]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Consolas", 8, QFont.Bold))
            lbl.setStyleSheet("color:#606080;background:transparent;")
            lbl.setFixedWidth(w)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            h0.addWidget(lbl)
        h0.addStretch()
        self._col0.addLayout(h0)
        self._fut_layout = QVBoxLayout()
        self._fut_layout.setSpacing(2)
        self._col0.addLayout(self._fut_layout)
        self._col0.addStretch()

        # Column 1: IBOV
        self._col1 = QVBoxLayout()
        self._col1.setSpacing(2)
        lbl_ibov = QLabel("IBOV ≥ 50%")
        lbl_ibov.setFont(QFont("Consolas", 9, QFont.Bold))
        lbl_ibov.setStyleSheet("color:#f0c040;background:transparent;")
        self._col1.addWidget(lbl_ibov)
        h1 = QHBoxLayout()
        h1.setSpacing(6)
        for txt, w, align in [("Ativo", 70, Qt.AlignmentFlag.AlignLeft),
                              ("Peso", 70, Qt.AlignmentFlag.AlignLeft),
                              ("Últ", 90, Qt.AlignmentFlag.AlignRight),
                              ("Var%", 70, Qt.AlignmentFlag.AlignRight)]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Consolas", 8, QFont.Bold))
            lbl.setStyleSheet("color:#606080;background:transparent;")
            lbl.setFixedWidth(w)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            h1.addWidget(lbl)
        h1.addStretch()
        self._col1.addLayout(h1)
        self._ibov_layout = QVBoxLayout()
        self._ibov_layout.setSpacing(2)
        self._col1.addLayout(self._ibov_layout)
        self._col1.addStretch()

        self._two_cols.addLayout(self._col0)
        self._two_cols.addLayout(self._col1)
        self._scroll_area.setWidget(self._scroll_content)
        l.addWidget(self._scroll_area, stretch=1)

        # Thermometer footer
        self._lbl_termometro = QLabel()
        self._lbl_termometro.setFont(QFont("Consolas", 10))
        self._lbl_termometro.setStyleSheet("color:#ccc;background:transparent;")
        l.addWidget(self._lbl_termometro)

    # ── Compass watermark ────────────────────────────────────────

    def _criar_rosa_dos_ventos(self, size: int) -> QPixmap:
        px = QPixmap(size, size)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        cx = cy = size // 2
        r = size * 0.40

        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        inner = QColor(255, 255, 255, 10)
        north = QColor(200, 60, 60, 18)

        for i in range(8):
            angle = math.radians(i * 45 - 90)
            is_ns = i % 4 == 0
            base_r = r * (0.38 if is_ns else 0.30)
            tip_r = r * (1.0 if is_ns else 0.75)
            x1 = cx + tip_r * math.cos(angle)
            y1 = cy + tip_r * math.sin(angle)
            a2 = angle + math.radians(22)
            a3 = angle - math.radians(22)
            x2 = cx + base_r * math.cos(a2)
            y2 = cy + base_r * math.sin(a2)
            x3 = cx + base_r * math.cos(a3)
            y3 = cy + base_r * math.sin(a3)
            pts = [QPointF(x1, y1), QPointF(x2, y2),
                   QPointF(cx, cy), QPointF(x3, y3)]
            p.setBrush(north if i == 0 else inner)
            p.drawPolygon(pts)

        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r * 0.65, r * 0.65)
        p.drawEllipse(QPointF(cx, cy), r * 0.85, r * 0.85)
        p.setPen(QPen(QColor(255, 255, 255, 10), 1))
        p.drawEllipse(QPointF(cx, cy), r * 0.50, r * 0.50)
        p.end()
        return px

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._compass_pixmap is None or self._compass_pixmap.size().width() != self.width() * 0.5:
            sz = int(self.width() * 0.5)
            self._compass_pixmap = self._criar_rosa_dos_ventos(sz)
        if self._compass_pixmap:
            p = QPainter(self)
            p.setOpacity(0.6)
            x = (self.width() - self._compass_pixmap.width()) // 2
            y = (self.height() - self._compass_pixmap.height()) // 2
            p.drawPixmap(x, y, self._compass_pixmap)
            p.end()

    # ── Data ─────────────────────────────────────────────────────

    def _inicializar(self):
        import logging
        log = logging.getLogger(__name__)
        try:
            self._carregar_cdi()
            self._mount_rows()
            log.info("SM _mount_rows: fut=%d ibov=%d", len(self._rows_fut), len(self._rows_ibov))
            self._criar_linhas()
            self._subscrever_todos()
            self._atualizar()
        except Exception as e:
            log.exception("SM erro em _inicializar: %s", e)
            self._atualizar()

    def _subscrever_todos(self):
        of = self._openfast
        if of is None or not hasattr(of, 'registrar_topico'):
            return
        import logging
        log = logging.getLogger(__name__)
        assinados: set[str] = set()
        for row in list(self._rows_fut) + list(self._rows_ibov):
            cod = row["cod"]
            if cod not in assinados:
                of.registrar_topico(cod, FieldName.LAST_PRICE)
                of.registrar_topico(cod, FieldName.BID)
                of.registrar_topico(cod, FieldName.ASK)
                assinados.add(cod)
                log.info("SM sub: %s LAST/BID/ASK", cod)
            pref = cod[:3]
            if len(cod) > 3 and pref not in assinados:
                of.registrar_topico(pref, FieldName.LAST_PRICE)
                assinados.add(pref)
                log.info("SM sub (prefixo): %s LAST", pref)

    def _carregar_cdi(self):
        try:
            p = ParametroRepository(self._db_path).get_by_chave("taxa_cdi")
            self._taxa_cdi = float(p.valor) if p else 0.1425
        except Exception:
            self._taxa_cdi = 0.1425

    def _mount_rows(self):
        hoje = date.today()
        a, m = hoje.year, hoje.month

        # Futures column — single current-month contract
        for prefixo, label in FUTUROS:
            cod = _cod(prefixo, a, m)
            venc = _venc_futuro(cod)
            self._rows_fut.append({
                "label": _limpar_nome_ativo(label), "cod": cod,
                "venc": venc.strftime("%d/%m/%y"),
                "_tem_var": True,
            })

        # Fixed contract futures (DI1F27, DI1F33)
        for cod, label, venc_date in FUTUROS_FIXOS:
            self._rows_fut.append({
                "label": _limpar_nome_ativo(label), "cod": cod,
                "venc": venc_date.strftime("%d/%m/%y"),
                "_tem_var": True,
            })

        # Nominal reference contracts (BRENT-CFD, EWZS-FMV)
        for cod, label in FUTUROS_NOMINAIS:
            self._rows_fut.append({
                "label": _limpar_nome_ativo(label), "cod": cod,
                "venc": "CONT",
                "_tem_var": True,
            })

        # IBOV column
        self._rows_ibov.append({"label": "IBOV", "cod": "IBOV", "peso": None})
        ibov_stocks = self._ibov_client.get_top50_percent()
        for st in ibov_stocks:
            ticker = str(st["ticker"])
            peso = float(st.get("peso", 0))
            self._rows_ibov.append({"label": ticker, "cod": ticker, "peso": peso})

    def _atualizar(self):
        self._carregar_cdi()
        of = self._openfast
        if of is not None and getattr(of, 'disponivel', False):
            self._lbl_status.setStyleSheet("background:#2ecc71;border-radius:5px;")
            self._lbl_status.setToolTip("Conectado")
        else:
            self._lbl_status.setStyleSheet("background:#f39c12;border-radius:5px;")
            self._lbl_status.setToolTip("Desconectado")
        self._atualizar_cdi()
        self._atualizar_precos()
        self._atualizar_analise()

    def _atualizar_cdi(self):
        if self._taxa_cdi <= 0:
            self._lbl_cdi.setText("CDI: —")
            return
        taxa_anual_pct = self._taxa_cdi * 100
        taxa_mensal_pct = (math.pow(1 + self._taxa_cdi, 1/12) - 1) * 100
        self._lbl_cdi.setText(f"CDI: {taxa_anual_pct:.2f}% a.a. | {taxa_mensal_pct:.2f}% a.m. 🟢")

    def _atualizar_precos(self):
        import logging
        log = logging.getLogger(__name__)
        of = self._openfast
        for rows in (self._rows_fut, self._rows_ibov):
            for item in rows:
                cod = item["cod"]
                last = None
                if of is not None:
                    last = of.ler_campo_cache(cod, FieldName.LAST_PRICE)
                    if last is None:
                        last = of.ler_campo_cache(cod, FieldName.BID)
                    if last is None:
                        last = of.ler_campo_cache(cod, FieldName.ASK)
                v = float(last) if last is not None else 0.0
                if cod not in self._ref_settled and v > 0:
                    if cod not in self._ref_prices:
                        self._ref_prices[cod] = v
                    self._ref_settled.add(cod)
                ref = self._ref_prices.get(cod) or v
                if v > 0:
                    var = ((v - ref) / ref * 100) if ref > 0 else 0.0
                    var_str = f"{var:+.2f}%"
                    var_float = var
                else:
                    var_str = "+0.00%"
                    var_float = 0.0
                cor = MarketAnalyzer.cor_heatmap(var_float)
                item["_last_raw"] = v
                item["_var"] = var_str
                item["_var_float"] = var_float
                item["_var_cor"] = cor
        if not self._primeira_poll_feita:
            self._primeira_poll_feita = True
            dump = {}
            for r in self._rows_fut:
                dump[f"F:{r['cod']}"] = f"{r.get('_last_raw', 0):.2f}" if r.get('_last_raw', 0) > 0 else "—"
            for r in self._rows_ibov:
                dump[f"I:{r['cod']}"] = f"{r.get('_last_raw', 0):.2f}" if r.get('_last_raw', 0) > 0 else "—"
            log.info("SM 1º tick: %s", dump)
        self._atualizar_labels()

    def _extrair_var(self, prefixo: str) -> float:
        for r in self._rows_fut:
            if r["cod"].startswith(prefixo.lower()):
                return r.get("_var_float", 0.0)
        return 0.0

    def _extrair_var_cod(self, cod: str) -> float:
        for r in self._rows_fut:
            if r["cod"].upper() == cod.upper():
                return r.get("_var_float", 0.0)
        return 0.0

    def _extrair_preco(self, cod: str) -> float:
        for r in self._rows_fut:
            if r["cod"].upper() == cod.upper():
                return r.get("_last_raw", 0.0)
        return 0.0

    def _extrair_pontos(self, cod: str) -> float:
        v = self._extrair_preco(cod)
        ref = self._ref_prices.get(cod.upper()) or self._ref_prices.get(cod.lower()) or v
        return v - ref if ref > 0 else 0.0

    def _atualizar_analise(self):
        win_var = self._extrair_var("WIN")
        wdo_var = self._extrair_var("WDO")
        di1f33_var = self._extrair_var_cod("DI1F33")
        di1f33_pontos = self._extrair_pontos("DI1F33")
        brent_var = self._extrair_var_cod("BRENT-CFD")
        sgx_var = self._extrair_var_cod("EWZS-FMV")

        curva, seta, curva_cor = MarketAnalyzer.analisar_curva_di(di1f33_pontos)
        vetor = MarketAnalyzer.analisar_vetor(
            win_var, wdo_var, di1f33_pontos,
            brent_var=brent_var, sgx_var=sgx_var,
        )
        vetor_cor = MarketAnalyzer.vetor_cor(vetor)

        self._lbl_curva.setText(
            f"Curva DI: {curva} {seta}"
        )
        self._lbl_curva.setStyleSheet(
            f"color:{curva_cor};background:transparent;font-weight:bold;"
        )

        emoji = {"RISK-ON": "🚀", "RISK-OFF": "⚠️", "COMMODITIES": "🛢️",
                 "DEFENSIVO": "🛡️", "MISTO": "🌀"}.get(vetor, "")
        self._lbl_vetor.setText(
            f"Vetor: {vetor}  {emoji}"
        )
        self._lbl_vetor.setStyleSheet(
            f"color:{vetor_cor};background:transparent;"
        )

        self._atualizar_termometro(vetor, vetor_cor)

    def _atualizar_termometro(self, vetor: str, cor: str):
        # Definição dos textos do termômetro com espaçamento de 2 espaços
        # O rodapé deve ter exatamente 2 espaços em branco antes da palavra "Pressão"
        prefixo_html = "<span style='color:#00f2ff;'>▋</span> <span style='color:#a0a0c0;'>Pressão</span> <span style='color:#00f2ff; font-weight: bold;'>[ℹ]</span><span style='color:#a0a0c0;'>:</span>"
        
        if vetor == "RISK-ON":
            cor_vetor = "#2ecc71"
            desc = "RISK-ON (Fluxo Comprador)"
            blocks_html = (
                "<span style='color:#4a5568;'>[</span> "
                "<span style='color:#2d2d44;'>░ ░ ░ ░ ░ </span>"
                "🟢 🟢 🟢 🟢 🟢 "
                "<span style='color:#4a5568;'>]</span>"
            )
        elif vetor == "RISK-OFF":
            cor_vetor = "#e74c3c"
            desc = "RISK-OFF (Fuga de Capital)"
            blocks_html = (
                "<span style='color:#4a5568;'>[</span> "
                "🔴 🔴 🔴 🔴 🔴 "
                "<span style='color:#2d2d44;'>░ ░ ░ ░ ░ </span>"
                "<span style='color:#4a5568;'>]</span>"
            )
        elif vetor == "COMMODITIES":
            cor_vetor = "#f0c040"
            desc = "COMMODITIES (Suporte de Carga)"
            blocks_html = (
                "<span style='color:#4a5568;'>[</span> "
                "<span style='color:#2d2d44;'>░ ░ ░ </span>"
                "🟡 🟡 🟡 🟡 "
                "<span style='color:#2d2d44;'>░ ░ ░ </span>"
                "<span style='color:#4a5568;'>]</span>"
            )
        elif vetor == "DEFENSIVO":
            cor_vetor = "#e67e22"
            desc = "FISCAL/DEFENSIVO (Aversão Local)"
            blocks_html = (
                "<span style='color:#4a5568;'>[</span> "
                "<span style='color:#2d2d44;'>░ ░ ░ </span>"
                "🟠 🟠 🟠 🟠 "
                "<span style='color:#2d2d44;'>░ ░ ░ </span>"
                "<span style='color:#4a5568;'>]</span>"
            )
        else: # MISTO ou padrão
            cor_vetor = "#9090b0"
            desc = "MISTO (Sem Direção Clara)"
            blocks_html = (
                "<span style='color:#4a5568;'>[</span> "
                "<span style='color:#2d2d44;'>░ ░ ░ ░ ░ ░ ░ ░ ░ ░ </span>"
                "<span style='color:#4a5568;'>]</span>"
            )

        html_content = (
            f"{prefixo_html} <span style='font-family:Consolas, monospace;'>{blocks_html}</span> "
            f"&nbsp;&nbsp;<span style='color:{cor_vetor}; font-weight: bold;'>{desc}</span>"
        )
        self._lbl_termometro.setText(html_content)
        self._lbl_termometro.setStyleSheet("background:transparent;")

    def _criar_linhas(self):
        ft = QFont("Consolas", 10)
        for rows, layout in [(self._rows_fut, self._fut_layout), (self._rows_ibov, self._ibov_layout)]:
            for item in rows:
                row = QHBoxLayout()
                row.setSpacing(6)
                labels: list[QLabel] = []
                if layout is self._fut_layout:
                    dados = [
                        (item["label"], 70, "#e0e0e0", Qt.AlignmentFlag.AlignLeft),
                        (item["venc"], 70, "#9090b0", Qt.AlignmentFlag.AlignLeft),
                        ("—", 90, "#ffffff", Qt.AlignmentFlag.AlignRight),
                        ("", 70, "#888", Qt.AlignmentFlag.AlignRight),
                    ]
                else:
                    p = item.get("peso")
                    peso_str = f"{p:.2f}%" if p is not None else "—"
                    peso_cor = "#f0c040" if p is not None else "#606080"
                    dados = [
                        (item["label"], 70, "#e0e0e0", Qt.AlignmentFlag.AlignLeft),
                        (peso_str, 70, peso_cor, Qt.AlignmentFlag.AlignLeft),
                        ("—", 90, "#ffffff", Qt.AlignmentFlag.AlignRight),
                        ("", 70, "#888", Qt.AlignmentFlag.AlignRight),
                    ]
                for txt, w, cor, align in dados:
                    lbl = QLabel(txt)
                    lbl.setFont(ft)
                    lbl.setFixedWidth(w)
                    lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                    lbl.setStyleSheet(f"color:{cor};background:transparent;")
                    row.addWidget(lbl)
                    labels.append(lbl)
                row.addStretch()
                c = QWidget()
                c.setStyleSheet("background:transparent;")
                c.setLayout(row)
                layout.addWidget(c)
                item["_labels"] = labels

    def _atualizar_labels(self):
        for rows in (self._rows_fut, self._rows_ibov):
            for item in rows:
                labels = item.get("_labels")
                if not labels:
                    continue
                v = item.get("_last_raw", 0)
                last_str = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(v, float) and v > 0 else "—"

                ativo_limpo = _limpar_nome_ativo(item["label"])

                is_ibov = "peso" in item
                if is_ibov:
                    p = item.get("peso")
                    venc_str = f"{p:.2f}%" if p is not None else "—"
                else:
                    venc_str = item.get("venc", "—")

                var_str = item.get("_var", "+0.00%")
                var_cor = item.get("_var_cor", "#888")
                v_float = item.get("_var_float", 0.0)

                ativo_f = f"{ativo_limpo:<8}"
                venc_f = f"{venc_str:<10}"
                ult_f = f"{last_str:>10}"
                var_f = f"{var_str:>8}"

                # label[0] = Ativo
                labels[0].setText(ativo_f)

                # label[1] = Venc ou Peso
                labels[1].setText(venc_f)
                if is_ibov:
                    p = item.get("peso")
                    labels[1].setStyleSheet(
                        "color:#f0c040;background:transparent;" if p is not None
                        else "color:#606080;background:transparent;"
                    )
                else:
                    labels[1].setStyleSheet("color:#9090b0;background:transparent;")

                # label[2] = Último
                labels[2].setText(ult_f)
                labels[2].setStyleSheet("color:#ffffff;background:transparent;")

                # label[3] = Var%
                if item.get("_last_raw", 0) > 0 and v_float <= -1.5:
                    lbl_style = "color:#ffffff;background:#e74c3c;padding:0 2px;"
                elif item.get("_last_raw", 0) > 0 and v_float >= 1.5:
                    lbl_style = "color:#000000;background:#2ecc71;padding:0 2px;"
                else:
                    lbl_style = f"color:{var_cor};background:transparent;padding:0 2px;"
                labels[3].setText(var_f)
                labels[3].setStyleSheet(lbl_style)

    # ── Window Events ────────────────────────────────────────────

    def closeEvent(self, event):
        self._timer.stop()
        self._timer.deleteLater()
        super().closeEvent(event)

    def _toggle_visivel(self, ev=None):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def restaurar(self):
        self.show()
        self.raise_()
        self.activateWindow()
