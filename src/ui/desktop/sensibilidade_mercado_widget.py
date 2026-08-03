from __future__ import annotations

import logging
import math
import threading
import time
from datetime import date, timedelta
from typing import Any

import numpy as np
from PySide6.QtCore import QPointF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
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
from src.infrastructure.persistence.database import get_db_path
from src.infrastructure.persistence.repositories.repositories import (
    ParametroRepository,
)

log = logging.getLogger(__name__)

_MC = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
       7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
_MC_INV = {v: k for k, v in _MC.items()}

ADR_MAP: dict[str, str] = {
    "VALE3": "VALE",
    "PETR4": "PBR",
    "PETR3": "PBR",
    "ITUB4": "ITUB",
    "BBDC4": "BBD",
    "BBDC3": "BBD",
    "ABEV3": "ABEV",
    "SBSP3": "SBS",
    "EMBJ3": "ERJ",
    "WEGE3": "WEGZY",
    "B3SA3": "BOLSY",
}

ADR_POLL_INTERVAL_S = 60
YFINANCE_TIMEOUT_S = 8
YFINANCE_MAX_RETRIES = 2

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


def _cod(prefixo: str, ano: int, mes: int) -> str:
    return f"{prefixo.lower()}{_MC[mes].lower()}{str(ano)[-2:]}"


def _prox_mes(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _limpar_nome_ativo(nome: str) -> str:
    if not nome:
        return ""
    nome = nome.replace("DI1 Jan/27", "DI1F27").replace("DI1 Jan/2", "DI1F27")
    nome = nome.replace("DI1 Jan/33", "DI1F33").replace("DI1 Jan/3", "DI1F33")
    return nome


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
    if p in ("DI1", "DI"):
        return _venc_di(mes, ano)
    return date(ano, mes, 1)


def _fmt_preco(v: float) -> str:
    if not isinstance(v, (int, float)) or v <= 0:
        return "—"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_var(var_pct: float) -> str:
    return f"{var_pct:+.2f}%" if var_pct else "+0.00%"


def _seta(var: float) -> str:
    if var > 0:
        return "▲"
    if var < 0:
        return "▼"
    return "─"


def _cor_direcao(var: float) -> str:
    if var > 0:
        return "#2ecc71"
    if var < 0:
        return "#e74c3c"
    return "#9090b0"


class _AdrFetcher(QThread):
    dados_atualizados = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._running = True
        self._mutex = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._tickers_unicos = sorted(set(ADR_MAP.values()))
        log.info("ADR Fetcher: tickers=%s", self._tickers_unicos)

    def obter(self, adr_cod: str) -> dict[str, Any] | None:
        with self._mutex:
            return self._cache.get(adr_cod)

    def parar(self):
        self._running = False

    def run(self):
        try:
            import yfinance as yf
        except ImportError as e:
            log.warning("ADR Fetcher: yfinance indisponível — %s", e)
            return

        while self._running:
            try:
                dados: dict[str, dict[str, Any]] = {}
                for tentativa in range(1, YFINANCE_MAX_RETRIES + 1):
                    try:
                        tickers_obj = yf.Tickers(" ".join(self._tickers_unicos))
                        for adr in self._tickers_unicos:
                            t = tickers_obj.tickers.get(adr)
                            if t is None:
                                continue
                            preco = None
                            anterior = None
                            try:
                                info = t.fast_info
                                preco = getattr(info, "last_price", None) or getattr(info, "regular_market_price", None)
                                anterior = getattr(info, "regular_market_previous_close", None) or getattr(info, "previous_close", None)
                            except Exception:
                                info = getattr(t, "info", None) or {}
                                preco = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                                anterior = info.get("previousClose") or info.get("regularMarketPreviousClose")
                            if preco and preco > 0:
                                var_pct = ((preco - anterior) / anterior * 100) if anterior and anterior > 0 else 0.0
                                dados[adr] = {
                                    "preco": float(preco),
                                    "anterior": float(anterior) if anterior else 0.0,
                                    "var_pct": round(var_pct, 2),
                                    "ts": time.time(),
                                }
                        break
                    except Exception as e:
                        if tentativa < YFINANCE_MAX_RETRIES:
                            log.warning("ADR fetch tentativa %d/%d falhou: %s", tentativa, YFINANCE_MAX_RETRIES, e)
                            time.sleep(2)
                        else:
                            raise

                if dados:
                    with self._mutex:
                        for adr, info in dados.items():
                            self._cache[adr] = info
                    self.dados_atualizados.emit(dados)
                    log.debug("ADR: %d tickers atualizados", len(dados))
            except Exception as e:
                log.warning("ADR fetch falhou (todas tentativas): %s", e)

            for _ in range(ADR_POLL_INTERVAL_S):
                if not self._running:
                    break
                time.sleep(1)


class SensibilidadeMercadoWidget(QWidget):
    def __init__(self, db_path: str | None = None, source=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._db_path = db_path or get_db_path()
        self._openfast = source
        self._ref_prices: dict[str, float] = {}
        self._ref_date: date | None = None
        self._rows_fut: list[dict[str, Any]] = []
        self._rows_ibov: list[dict[str, Any]] = []
        self._taxa_cdi = 0.0
        self._cdi_ultima_leitura = 0.0
        self._cdi_cache_interval_s = 300
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar)
        self._primeira_poll_feita = False
        self._ibov_client = IbovCompositionClient()
        self._compass_pixmap: QPixmap | None = None
        self._adr_fetcher = _AdrFetcher(self)
        self._adr_fetcher.dados_atualizados.connect(self._on_adr_atualizado)
        self._adr_cache: dict[str, dict[str, Any]] = {}

        self._setup_ui()
        self._inicializar()
        self._timer.start(3000)
        self._adr_fetcher.start()

    def _setup_ui(self):
        self.setWindowTitle("Sensibilidade de Mercado")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(700, 480)
        self.resize(820, 600)

        self.setStyleSheet("""
            SensibilidadeMercadoWidget {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #14142a, stop:1 #0e0e1a);
            }
        """)

        l = QVBoxLayout(self)
        l.setContentsMargins(8, 4, 8, 8)
        l.setSpacing(4)

        self._lbl_status = QLabel()
        self._lbl_status.setFixedSize(10, 10)
        self._lbl_status.setStyleSheet("background:#f39c12;border-radius:5px;")

        cdi_row = QHBoxLayout()
        cdi_row.setSpacing(6)
        self._lbl_cdi = QLabel()
        self._lbl_cdi.setFont(QFont("Consolas", 10))
        self._lbl_cdi.setStyleSheet("color:#0ff;background:transparent;")
        cdi_row.addWidget(self._lbl_cdi)
        cdi_row.addWidget(self._lbl_status)
        cdi_row.addStretch()
        l.addLayout(cdi_row)

        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(6)
        self._card_dolar = self._criar_card("D\u00d3LAR", ["WIN", "WDO"])
        self._card_juros = self._criar_card("JUROS", ["DI1F33", "CURVA"])
        self._card_commo = self._criar_card("COMMODITIES", ["BRENT", "EWZS"])
        self._card_vetor = self._criar_card("VETOR", ["STATUS"])
        self._cards_row.addWidget(self._card_dolar["frame"])
        self._cards_row.addWidget(self._card_juros["frame"])
        self._cards_row.addWidget(self._card_commo["frame"])
        self._cards_row.addWidget(self._card_vetor["frame"])
        l.addLayout(self._cards_row)

        s = QFrame()
        s.setFrameShape(QFrame.HLine)
        s.setStyleSheet("color:#2d2d44;")
        l.addWidget(s)

        ibov_row = QHBoxLayout()
        ibov_row.setSpacing(8)
        self._lbl_ibov_label = QLabel("IBOV")
        self._lbl_ibov_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self._lbl_ibov_label.setFixedWidth(50)
        self._lbl_ibov_label.setStyleSheet("color:#f0c040;background:transparent;")
        ibov_row.addWidget(self._lbl_ibov_label)

        self._ibov_bar = QProgressBar()
        self._ibov_bar.setTextVisible(False)
        self._ibov_bar.setFixedHeight(14)
        self._ibov_bar.setRange(0, 100)
        self._ibov_bar.setValue(50)
        self._ibov_bar.setStyleSheet("""
            QProgressBar {
                background: #1a1a30;
                border: 1px solid #2d2d44;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #2ecc71, stop:0.5 #f0c040, stop:1 #e74c3c);
                border-radius: 3px;
            }
        """)
        ibov_row.addWidget(self._ibov_bar, stretch=1)

        self._lbl_ibov_val = QLabel("—")
        self._lbl_ibov_val.setFont(QFont("Consolas", 10, QFont.Bold))
        self._lbl_ibov_val.setStyleSheet("color:#fff;background:transparent;")
        self._lbl_ibov_val.setFixedWidth(120)
        self._lbl_ibov_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ibov_row.addWidget(self._lbl_ibov_val)

        self._lbl_ibov_var = QLabel("+0.00%")
        self._lbl_ibov_var.setFont(QFont("Consolas", 10, QFont.Bold))
        self._lbl_ibov_var.setFixedWidth(80)
        self._lbl_ibov_var.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ibov_row.addWidget(self._lbl_ibov_var)
        l.addLayout(ibov_row)

        s2 = QFrame()
        s2.setFrameShape(QFrame.HLine)
        s2.setStyleSheet("color:#2d2d44;")
        l.addWidget(s2)

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
        self._grid = QGridLayout(self._scroll_content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(1)
        self._grid.setColumnStretch(0, 0)
        self._grid.setColumnStretch(1, 0)
        self._grid.setColumnStretch(2, 0)
        self._grid.setColumnStretch(3, 0)
        self._grid.setColumnStretch(4, 0)
        self._grid.setColumnStretch(5, 1)
        self._scroll_area.setWidget(self._scroll_content)
        l.addWidget(self._scroll_area, stretch=1)

        self._lbl_termometro = QLabel()
        self._lbl_termometro.setFont(QFont("Consolas", 10))
        self._lbl_termometro.setStyleSheet("color:#ccc;background:transparent;")
        l.addWidget(self._lbl_termometro)

    def _criar_card(self, titulo: str, linhas: list[str]) -> dict[str, Any]:
        frame = QFrame()
        frame.setFixedHeight(70)
        frame.setStyleSheet("""
            QFrame {
                background: #1a1a30;
                border: 1px solid #2d2d44;
                border-radius: 6px;
            }
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 4, 8, 4)
        fl.setSpacing(2)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setFont(QFont("Consolas", 8, QFont.Bold))
        lbl_titulo.setStyleSheet("color:#606080;background:transparent;border:none;")
        fl.addWidget(lbl_titulo)

        line_labels: list[QLabel] = []
        for _ in linhas:
            lbl = QLabel("—")
            lbl.setFont(QFont("Consolas", 9))
            lbl.setStyleSheet("color:#ccc;background:transparent;border:none;")
            fl.addWidget(lbl)
            line_labels.append(lbl)

        fl.addStretch()
        return {"frame": frame, "title": lbl_titulo, "lines": line_labels}

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._compass_pixmap is None or self._compass_pixmap.size().width() != int(self.width() * 0.4):
            sz = int(self.width() * 0.4)
            self._compass_pixmap = self._criar_rosa_dos_ventos(sz)
        if self._compass_pixmap:
            p = QPainter(self)
            p.setOpacity(0.35)
            x = (self.width() - self._compass_pixmap.width()) // 2
            y = (self.height() - self._compass_pixmap.height()) // 2
            p.drawPixmap(x, y, self._compass_pixmap)
            p.end()

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
            pts = [QPointF(x1, y1), QPointF(x2, y2), QPointF(cx, cy), QPointF(x3, y3)]
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

    def _inicializar(self):
        try:
            self._carregar_cdi()
            self._mount_rows()
            log.info("SM _mount_rows: fut=%d ibov=%d", len(self._rows_fut), len(self._rows_ibov))
            self._criar_grid_header()
            self._criar_grid_rows()
            self._subscrever_todos()
            self._atualizar()
        except Exception as e:
            log.exception("SM erro em _inicializar: %s", e)
            self._atualizar()

    def _subscrever_todos(self):
        of = self._openfast
        if of is None or not hasattr(of, "registrar_topico"):
            return
        assinados: set[str] = set()
        for row in list(self._rows_fut) + list(self._rows_ibov):
            cod = row["cod"]
            br_alt = row.get("_br_alt")
            for c in [cod] + ([br_alt] if br_alt else []):
                if c not in assinados:
                    of.registrar_topico(c, FieldName.LAST_PRICE)
                    of.registrar_topico(c, FieldName.BID)
                    of.registrar_topico(c, FieldName.ASK)
                    of.registrar_topico(c, FieldName.CLOSE)
                    of.registrar_topico(c, FieldName.VARIATION)
                    assinados.add(c)
                    log.info("SM sub: %s LAST/BID/ASK/CLOSE/VAR", c)

    def _carregar_cdi(self):
        agora = time.time()
        if self._cdi_ultima_leitura > 0 and (agora - self._cdi_ultima_leitura) < self._cdi_cache_interval_s:
            return
        p = ParametroRepository(self._db_path).get_by_chave("taxa_cdi")
        self._taxa_cdi = float(p.valor)
        self._cdi_ultima_leitura = agora

    def _mount_rows(self):
        hoje = date.today()
        a, m = hoje.year, hoje.month

        for prefixo, label in FUTUROS:
            for am in ((a, m), _prox_mes(a, m)):
                cod = _cod(prefixo, *am)
                venc = _venc_futuro(cod)
                self._rows_fut.append({
                    "label": _limpar_nome_ativo(label),
                    "cod": cod,
                    "venc": venc.strftime("%d/%m/%y"),
                })

        for cod, label, venc_date in FUTUROS_FIXOS:
            self._rows_fut.append({
                "label": _limpar_nome_ativo(label),
                "cod": cod,
                "venc": venc_date.strftime("%d/%m/%y"),
            })

        for cod, label in FUTUROS_NOMINAIS:
            self._rows_fut.append({
                "label": _limpar_nome_ativo(label),
                "cod": cod,
                "venc": "CONT",
            })

        self._rows_ibov.append({
            "label": "IBOV", "cod": "IBOV", "peso": None, "_adr": None, "_br_alt": None,
        })
        ibov_stocks = self._ibov_client.get_top50_percent()
        for st in ibov_stocks:
            ticker = str(st["ticker"])
            peso = float(st.get("peso", 0))
            adr = ADR_MAP.get(ticker)
            alt = None
            if ticker == "PETR4":
                alt = "PETR3"
            elif ticker == "PETR3":
                continue
            elif ticker == "BBDC4":
                alt = "BBDC3"
            elif ticker == "BBDC3":
                continue
            self._rows_ibov.append({
                "label": ticker, "cod": ticker, "peso": peso, "_adr": adr, "_br_alt": alt,
            })

    def _criar_grid_header(self):
        headers = [
            ("Ativo", 80, Qt.AlignmentFlag.AlignLeft),
            ("Peso", 70, Qt.AlignmentFlag.AlignLeft),
            ("BR", 90, Qt.AlignmentFlag.AlignRight),
            ("ADR", 90, Qt.AlignmentFlag.AlignRight),
            ("Var%", 70, Qt.AlignmentFlag.AlignRight),
        ]
        for col, (txt, w, align) in enumerate(headers):
            lbl = QLabel(txt)
            lbl.setFont(QFont("Consolas", 8, QFont.Bold))
            lbl.setStyleSheet("color:#606080;background:transparent;")
            lbl.setFixedWidth(w)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            self._grid.addWidget(lbl, 0, col)

    def _criar_grid_rows(self):
        ft = QFont("Consolas", 10)
        all_rows = self._rows_fut + self._rows_ibov
        for i, item in enumerate(all_rows):
            row_n = i + 1
            labels: list[QLabel] = []

            label_str = _limpar_nome_ativo(item.get("label", ""))
            is_ibov = "peso" in item

            if is_ibov:
                p = item.get("peso")
                peso_str = f"{p:.2f}%" if p is not None else "—"
                peso_cor = "#f0c040" if p is not None else "#606080"
                col_data = [
                    (label_str, 80, "#e0e0e0", Qt.AlignmentFlag.AlignLeft),
                    (peso_str, 70, peso_cor, Qt.AlignmentFlag.AlignLeft),
                    ("—", 90, "#ffffff", Qt.AlignmentFlag.AlignRight),
                    ("—", 90, "#888", Qt.AlignmentFlag.AlignRight),
                    ("", 70, "#888", Qt.AlignmentFlag.AlignRight),
                ]
            else:
                venc_str = item.get("venc", "—")
                col_data = [
                    (label_str, 80, "#e0e0e0", Qt.AlignmentFlag.AlignLeft),
                    (venc_str, 70, "#9090b0", Qt.AlignmentFlag.AlignLeft),
                    ("—", 90, "#ffffff", Qt.AlignmentFlag.AlignRight),
                    ("—", 90, "#888", Qt.AlignmentFlag.AlignRight),
                    ("", 70, "#888", Qt.AlignmentFlag.AlignRight),
                ]

            for col, (txt, w, cor, align) in enumerate(col_data):
                lbl = QLabel(txt)
                lbl.setFont(ft)
                lbl.setFixedWidth(w)
                lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                lbl.setStyleSheet(f"color:{cor};background:transparent;")
                self._grid.addWidget(lbl, row_n, col)
                labels.append(lbl)

            item["_labels"] = labels
            item["_is_ibov"] = is_ibov

    def _atualizar(self):
        try:
            self._carregar_cdi()
            of = self._openfast
            if of is not None and getattr(of, "disponivel", False):
                self._lbl_status.setStyleSheet("background:#2ecc71;border-radius:5px;")
                self._lbl_status.setToolTip("Conectado")
            else:
                self._lbl_status.setStyleSheet("background:#f39c12;border-radius:5px;")
                self._lbl_status.setToolTip("Desconectado")
            self._atualizar_cdi()
            self._atualizar_precos()
            self._atualizar_analise()
        except Exception as e:
            log.exception("SM erro em _atualizar: %s", e)

    def _resetar_ref_se_necessario(self):
        hoje = date.today()
        if self._ref_date != hoje:
            self._ref_prices.clear()
            self._ref_date = hoje

    def _atualizar_cdi(self):
        if self._taxa_cdi <= 0:
            self._lbl_cdi.setText("CDI: —")
            return
        taxa_anual_pct = self._taxa_cdi * 100
        taxa_mensal_pct = (math.pow(1 + self._taxa_cdi, 1 / 12) - 1) * 100
        self._lbl_cdi.setText(f"CDI: {taxa_anual_pct:.2f}% a.a. | {taxa_mensal_pct:.2f}% a.m.")

    def _atualizar_precos(self):
        of = self._openfast
        self._resetar_ref_se_necessario()

        for rows in (self._rows_fut, self._rows_ibov):
            for item in rows:
                cod = item["cod"]
                var_oficial = None
                close_oficial = None
                if of is not None:
                    last = of.ler_campo_cache(cod, FieldName.LAST_PRICE)
                    if last in (None, 0.0):
                        last = of.ler_campo_cache(cod, FieldName.BID)
                    if last in (None, 0.0):
                        last = of.ler_campo_cache(cod, FieldName.ASK)
                    var_oficial = of.ler_campo_cache(cod, FieldName.VARIATION)
                    close_oficial = of.ler_campo_cache(cod, FieldName.CLOSE)
                v = float(last) if last is not None and last > 0 else 0.0

                if var_oficial is not None and isinstance(var_oficial, (int, float)) and var_oficial != 0.0:
                    var_float = float(var_oficial)
                    var_str = _fmt_var(var_float)
                elif close_oficial is not None and isinstance(close_oficial, (int, float)) and close_oficial > 0 and v > 0:
                    var_float = ((v - float(close_oficial)) / float(close_oficial) * 100.0)
                    var_str = _fmt_var(var_float)
                else:
                    if cod not in self._ref_prices and v > 0:
                        self._ref_prices[cod] = v
                    ref = self._ref_prices.get(cod, v)
                    if v > 0 and ref > 0:
                        var_float = ((v - ref) / ref * 100)
                        var_str = _fmt_var(var_float)
                    else:
                        var_str = "+0.00%"
                        var_float = 0.0

                cor = MarketAnalyzer.cor_heatmap(var_float)
                item["_last_raw"] = v
                item["_var"] = var_str
                item["_var_float"] = var_float
                item["_var_cor"] = cor

                br_alt = item.get("_br_alt")
                if br_alt:
                    alt_v = 0.0
                    if of is not None:
                        alt_last = of.ler_campo_cache(br_alt, FieldName.LAST_PRICE)
                        if alt_last in (None, 0.0):
                            alt_last = of.ler_campo_cache(br_alt, FieldName.BID)
                        if alt_last in (None, 0.0):
                            alt_last = of.ler_campo_cache(br_alt, FieldName.ASK)
                    alt_v = float(alt_last) if alt_last is not None and alt_last > 0 else 0.0
                    item["_br_alt_raw"] = alt_v

        if not self._primeira_poll_feita:
            self._primeira_poll_feita = True
            dump = {}
            for r in self._rows_fut:
                dump[f"F:{r['cod']}"] = _fmt_preco(r.get("_last_raw", 0))
            for r in self._rows_ibov:
                dump[f"I:{r['cod']}"] = _fmt_preco(r.get("_last_raw", 0))
            log.info("SM 1º tick: %s", dump)

        self._atualizar_labels()

    def _update_adr_in_row(self, item: dict[str, Any]):
        adr_cod = item.get("_adr")
        if not adr_cod:
            return
        adr_info = self._adr_fetcher.obter(adr_cod)
        if adr_info is None:
            item["_adr_raw"] = 0.0
            item["_adr_var"] = 0.0
            item["_adr_var_str"] = "—"
            return
        item["_adr_raw"] = adr_info.get("preco", 0.0)
        item["_adr_var"] = adr_info.get("var_pct", 0.0)
        item["_adr_var_str"] = _fmt_var(adr_info.get("var_pct", 0.0))

    def _atualizar_labels(self):
        for rows in (self._rows_fut, self._rows_ibov):
            for item in rows:
                self._update_adr_in_row(item)

                labels = item.get("_labels")
                if not labels:
                    continue

                v = item.get("_last_raw", 0)
                last_str = _fmt_preco(v)
                is_ibov = item.get("_is_ibov", False)

                if is_ibov:
                    p = item.get("peso")
                    venc_str = f"{p:.2f}%" if p is not None else "—"
                else:
                    venc_str = item.get("venc", "—")

                var_str = item.get("_var", "+0.00%")
                var_cor = item.get("_var_cor", "#888")
                v_float = item.get("_var_float", 0.0)

                adr_raw = item.get("_adr_raw", 0)
                adr_str = _fmt_preco(adr_raw) if item.get("_adr") else "—"

                labels[0].setText(f"{_limpar_nome_ativo(item['label']):<10}")
                labels[1].setText(f"{venc_str:<10}")
                if is_ibov:
                    p = item.get("peso")
                    labels[1].setStyleSheet(
                        "color:#f0c040;background:transparent;" if p is not None
                        else "color:#606080;background:transparent;"
                    )
                else:
                    labels[1].setStyleSheet("color:#9090b0;background:transparent;")

                labels[2].setText(f"{last_str:>10}")
                labels[2].setStyleSheet("color:#ffffff;background:transparent;")

                labels[3].setText(f"{adr_str:>10}")
                adr_cod = item.get("_adr")
                if adr_cod:
                    labels[3].setStyleSheet("color:#0cf;background:transparent;")
                else:
                    labels[3].setStyleSheet("color:#606080;background:transparent;")

                labels[4].setText(f"{var_str:>8}")
                if v > 0 and v_float <= -1.5:
                    labels[4].setStyleSheet("color:#ffffff;background:#e74c3c;padding:0 2px;")
                elif v > 0 and v_float >= 1.5:
                    labels[4].setStyleSheet("color:#000000;background:#2ecc71;padding:0 2px;")
                else:
                    labels[4].setStyleSheet(f"color:{var_cor};background:transparent;padding:0 2px;")

        self._atualizar_ibov_bar()

    def _atualizar_ibov_bar(self):
        ibov_item = None
        for r in self._rows_ibov:
            if r["cod"] == "IBOV":
                ibov_item = r
                break
        if ibov_item is None:
            return

        v = ibov_item.get("_last_raw", 0)
        var = ibov_item.get("_var_float", 0)
        self._lbl_ibov_val.setText(_fmt_preco(v))
        self._lbl_ibov_var.setText(_fmt_var(var))
        cor = _cor_direcao(var)
        self._lbl_ibov_var.setStyleSheet(f"color:{cor};background:transparent;font-weight:bold;")
        self._lbl_ibov_label.setStyleSheet("color:#f0c040;background:transparent;font-weight:bold;")

        barra_val = max(0, min(100, 50 + var * 5))
        self._ibov_bar.setValue(int(barra_val))

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
        ref = self._ref_prices.get(cod.upper(), v)
        return v - ref if ref > 0 else 0.0

    def _atualizar_analise(self):
        win_var = self._extrair_var("win")
        wdo_var = self._extrair_var("wdo")
        di1f33_pontos = self._extrair_pontos("DI1F33")
        brent_var = self._extrair_var_cod("BRENT-CFD")
        sgx_var = self._extrair_var_cod("EWZS-FMV")
        di1f33_preco = self._extrair_preco("DI1F33")

        curva, seta_c, curva_cor = MarketAnalyzer.analisar_curva_di(di1f33_pontos)
        vetor = MarketAnalyzer.analisar_vetor(
            win_var, wdo_var, di1f33_pontos,
            brent_var=brent_var, sgx_var=sgx_var,
        )
        vetor_cor = MarketAnalyzer.vetor_cor(vetor)

        emoji_vetor = {"RISK-ON": "🚀", "RISK-OFF": "⚠️", "COMMODITIES": "🛢️",
                       "DEFENSIVO": "🛡️", "MISTO": "🌀"}.get(vetor, "")

        self._card_dolar["lines"][0].setText(
            f"<span style='color:{_cor_direcao(win_var)}'>{_seta(win_var)} WIN {_fmt_var(win_var)}</span>"
        )
        self._card_dolar["lines"][0].setStyleSheet("color:#ccc;background:#1a1a30;border:none;")
        self._card_dolar["lines"][1].setText(
            f"<span style='color:{_cor_direcao(wdo_var)}'>{_seta(wdo_var)} WDO {_fmt_var(wdo_var)}</span>"
        )
        self._card_dolar["lines"][1].setStyleSheet("color:#ccc;background:#1a1a30;border:none;")

        self._card_juros["lines"][0].setText(
            f"<span style='color:{_cor_direcao(di1f33_pontos)}'>DI1F33 {di1f33_preco:.2f}</span>"
        )
        self._card_juros["lines"][0].setStyleSheet("color:#ccc;background:#1a1a30;border:none;")
        self._card_juros["lines"][1].setText(
            f"<span style='color:{curva_cor};font-weight:bold;'>{curva} {seta_c}</span>"
        )
        self._card_juros["lines"][1].setStyleSheet(f"color:{curva_cor};background:#1a1a30;border:none;font-weight:bold;")

        self._card_commo["lines"][0].setText(
            f"<span style='color:{_cor_direcao(brent_var)}'>{_seta(brent_var)} BRENT {_fmt_var(brent_var)}</span>"
        )
        self._card_commo["lines"][0].setStyleSheet("color:#ccc;background:#1a1a30;border:none;")
        self._card_commo["lines"][1].setText(
            f"<span style='color:{_cor_direcao(sgx_var)}'>{_seta(sgx_var)} EWZS {_fmt_var(sgx_var)}</span>"
        )
        self._card_commo["lines"][1].setStyleSheet("color:#ccc;background:#1a1a30;border:none;")

        self._card_vetor["lines"][0].setText(
            f"<span style='color:{vetor_cor};font-weight:bold;font-size:12px;'>{vetor}  {emoji_vetor}</span>"
        )
        self._card_vetor["lines"][0].setStyleSheet(
            f"color:{vetor_cor};background:#1a1a30;border:none;font-weight:bold;"
        )

        self._atualizar_termometro(vetor, vetor_cor)

        self._atualizar_bordas_cards(win_var, wdo_var, di1f33_pontos, brent_var, vetor)

    def _atualizar_bordas_cards(self, win_var: float, wdo_var: float, di1f33_pontos: float, brent_var: float, vetor: str):
        cor_dolar = _cor_direcao(win_var) if abs(win_var) >= abs(wdo_var) else _cor_direcao(wdo_var)
        if win_var == 0 and wdo_var == 0:
            cor_dolar = "#2d2d44"

        cor_juros = "#e74c3c" if di1f33_pontos > 0 else "#2ecc71" if di1f33_pontos < 0 else "#2d2d44"

        cor_commo = _cor_direcao(brent_var)

        vetor_cor_map = {"RISK-ON": "#2ecc71", "RISK-OFF": "#e74c3c", "COMMODITIES": "#f0c040",
                         "DEFENSIVO": "#e67e22", "MISTO": "#9090b0"}
        cor_vetor = vetor_cor_map.get(vetor, "#2d2d44")

        for card_key, cor_borda in [("_card_dolar", cor_dolar), ("_card_juros", cor_juros),
                                     ("_card_commo", cor_commo), ("_card_vetor", cor_vetor)]:
            card = getattr(self, card_key, None)
            if card:
                card["frame"].setStyleSheet(f"""
                    QFrame {{
                        background: #1a1a30;
                        border: 1px solid #2d2d44;
                        border-left: 3px solid {cor_borda};
                        border-radius: 6px;
                    }}
                """)

    def _atualizar_termometro(self, vetor: str, _cor: str):
        prefixo_html = (
            "<span style='color:#00f2ff;'>▋</span> "
            "<span style='color:#a0a0c0;'>Pressão</span> "
            "<span style='color:#00f2ff; font-weight: bold;'>[ℹ]</span>"
            "<span style='color:#a0a0c0;'>:</span>"
        )

        if vetor == "RISK-ON":
            cor_vetor = "#2ecc71"
            desc = "RISK-ON (Fluxo Comprador)"
            blocks = ("[ 🟢 🟢 🟢 🟢 🟢 ░ ░ ░ ░ ░ ]")
        elif vetor == "RISK-OFF":
            cor_vetor = "#e74c3c"
            desc = "RISK-OFF (Fuga de Capital)"
            blocks = ("[ 🔴 🔴 🔴 🔴 🔴 ░ ░ ░ ░ ░ ]")
        elif vetor == "COMMODITIES":
            cor_vetor = "#f0c040"
            desc = "COMMODITIES (Suporte de Carga)"
            blocks = ("[ ░ ░ ░ 🟡 🟡 🟡 🟡 ░ ░ ░ ]")
        elif vetor == "DEFENSIVO":
            cor_vetor = "#e67e22"
            desc = "FISCAL/DEFENSIVO (Aversão Local)"
            blocks = ("[ ░ ░ ░ 🟠 🟠 🟠 🟠 ░ ░ ░ ]")
        else:
            cor_vetor = "#9090b0"
            desc = "MISTO (Sem Direção Clara)"
            blocks = ("[ ░ ░ ░ ░ ░ ░ ░ ░ ░ ░ ]")

        html = (
            f"{prefixo_html} <span style='font-family:Consolas,monospace;'>{blocks}</span>"
            f"&nbsp;&nbsp;<span style='color:{cor_vetor};font-weight:bold;'>{desc}</span>"
        )
        self._lbl_termometro.setText(html)
        self._lbl_termometro.setStyleSheet("background:transparent;")

    def _on_adr_atualizado(self, dados: dict):
        pass

    def closeEvent(self, event):
        self._timer.stop()
        self._timer.deleteLater()
        self._adr_fetcher.parar()
        self._adr_fetcher.wait(3000)
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
