from collections import Counter
import math

from scipy.stats import norm

from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal, QUrl, QRect
from PySide6.QtGui import QFont, QColor, QBrush, QDesktopServices, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QFrame, QWidget,
    QStyledItemDelegate, QStyleOptionViewItem, QDoubleSpinBox, QRadioButton, QButtonGroup, QCheckBox,
)

from src.ui.desktop.column_utils import salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas
from src.ui.desktop.theme import Palette

CUSTOS_DISCLOSURE = (
    "\n\n* Custos ja incluem taxa B3 (emolumento 0,025%% + liquidacao 0,0275%% por perna) "
    "e IR (15%% sobre o lucro liquido)."
)


def _formatar_detectado(detectado_em):
    if detectado_em is None:
        return ""
    from zoneinfo import ZoneInfo
    dt = detectado_em
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/Sao_Paulo"))
    return dt.strftime("%d/%m/%Y %H:%M:%S")


PUT_RATIO_COLUMNS = [
    ("Ativo", "ativo"),
    ("Spot", "spot"),
    ("Ratio", "ratio_label"),
    ("K1", "strike_k1"),
    ("K2", "strike_k2"),
    ("Ask K1", "ask_put_k1"),
    ("Bid K2", "bid_put_k2"),
    ("Credito", "credito_bruto"),
    ("Yield%", "credit_yield"),
    ("x CDI", "yield_cdi"),
    ("Prot%", "protecao_pct"),
    ("BE", "be_down"),
    ("POP%", "pop_pct"),
    ("Perfil", "perfil"),
    ("IV Rank", "iv_rank"),
    ("IV Pct", "iv_percentile"),
    ("Score", "score"),
    ("Zona", "zona"),
    ("Dias", "dias"),
    ("Venc", "vencimento"),
    ("Put K1", "cod_put_k1"),
    ("Put K2", "cod_put_k2"),
    ("IV PUT", "iv_put_pct"),
    ("Q K1", "qtd_ask_put_k1"),
    ("Q K2", "qtd_bid_put_k2"),
    ("Detectado", "label_detectado"),
]


def _perfil_payoff(r) -> tuple:
    spot = r.spot
    be = r.be_down
    K1 = r.strike_k1
    iv = getattr(r, 'iv_put_pct', 0.0) / 100.0
    T = r.dias / 365.0
    if spot <= 0 or iv <= 0 or T <= 0 or K1 <= 0:
        return 0, 0, 0
    sigma_periodo = iv * math.sqrt(T)
    d_K1 = (spot - K1) / (spot * sigma_periodo) if spot > K1 else 0.0
    d_BE = (spot - be) / (spot * sigma_periodo) if spot > be else 0.0
    p_credit = norm.cdf(d_K1) * 100.0
    p_slope = max(0.0, (norm.cdf(d_BE) - norm.cdf(d_K1)) * 100.0)
    p_loss = max(0.0, 100.0 - p_credit - p_slope)
    return p_loss, p_slope, p_credit


class _PerfilDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        rect = option.rect
        painter.setRenderHint(QPainter.Antialiasing)

        val = index.data(Qt.ItemDataRole.UserRole)
        if not val or not isinstance(val, tuple):
            painter.restore()
            return
        p_loss, p_slope, p_credit = val
        if p_credit + p_slope + p_loss <= 0:
            painter.restore()
            return

        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor("#1a2a4a"))

        margin = 4
        w, h = rect.width() - margin * 2, rect.height() - 8
        x0, y0 = rect.x() + margin, rect.y() + 4
        total = p_loss + p_slope + p_credit

        w_loss = int(w * p_loss / total)
        w_slope = int(w * p_slope / total)
        w_credit = w - w_loss - w_slope

        # Fundo area perda
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2d1010"))
        painter.drawRoundedRect(QRect(x0, y0, w_loss, h), 3, 3)
        # Fundo area tenda
        painter.setBrush(QColor("#102d10"))
        painter.drawRoundedRect(QRect(x0 + w_loss, y0, w_slope, h), 3, 3)
        # Fundo area credito
        painter.setBrush(QColor("#101a2d"))
        painter.drawRoundedRect(QRect(x0 + w_loss + w_slope, y0, w_credit, h), 3, 3)

        # Linha do payoff
        y_top = y0 + 4
        y_mid = y0 + h // 2
        y_bot = y0 + h - 4
        pen = QPen(QColor("#e0e0e0"), 1.5)
        painter.setPen(pen)

        path = QPainterPath()
        # Loss zone: linha reta no fundo (prejuizo maximo)
        path.moveTo(x0, y_bot)
        path.lineTo(x0 + w_loss, y_bot)
        # Slope zone: diagonal subindo do fundo ate o topo
        path.lineTo(x0 + w_loss + w_slope, y_top)
        # Credit zone: linha reta no topo (credito)
        path.lineTo(x0 + w_loss + w_slope + w_credit, y_top)
        painter.drawPath(path)

        # BE linha tracejada
        pen_be = QPen(QColor("#ef5350"), 0.8, Qt.DashLine)
        painter.setPen(pen_be)
        be_x = x0 + w_loss
        painter.drawLine(be_x, y0, be_x, y0 + h)

        # K1 linha pontilhada
        pen_k1 = QPen(QColor("#42a5f5"), 0.6, Qt.DotLine)
        painter.setPen(pen_k1)
        k1_x = x0 + w_loss + w_slope
        painter.drawLine(k1_x, y0, k1_x, y0 + h)

        # Percentuais
        font = QFont("Consolas", 7, QFont.Bold)
        painter.setFont(font)
        if p_loss >= 5:
            painter.setPen(QColor("#ef5350"))
            painter.drawText(QRect(x0, y0 + h - 14, w_loss, 12), Qt.AlignCenter, f"{p_loss:.0f}%")
        if p_credit >= 5:
            painter.setPen(QColor("#42a5f5"))
            painter.drawText(QRect(x0 + w_loss + w_slope, y0, w_credit, 12), Qt.AlignCenter, f"{p_credit:.0f}%")

        painter.restore()

    def sizeHint(self, option, index):
        return __import__('PySide6.QtCore').QSize(200, 28)


class PutRatioTableModel(QAbstractTableModel):
    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(PUT_RATIO_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(PUT_RATIO_COLUMNS):
            if role == Qt.ItemDataRole.DisplayRole:
                return PUT_RATIO_COLUMNS[section][0]
            if role == Qt.ItemDataRole.ToolTipRole:
                tips = {
                    "ativo": "Codigo da acao objeto.",
                    "spot": "Preco atual do ativo (Ask do book RTD).",
                    "ratio_label": "Proporcao N1xN2: compra N1 Puts K1, vende N2 Puts K2.",
                    "strike_k1": "Strike da Put COMPRADA (K1 > K2). Ideal: 3-15% abaixo do spot.",
                    "strike_k2": "Strike da Put VENDIDA (K2 < K1). 1 a 3 strikes abaixo de K1.",
                    "ask_put_k1": "Preco Ask da Put K1 — voce PAGA isso para comprar a protecao.",
                    "bid_put_k2": "Preco Bid da Put K2 — voce RECEBE isso ao vender a descoberto.",
                    "credito_bruto": "Credito liquido = N2*Bid_K2 - N1*Ask_K1. Deve ser positivo.",
                    "credit_yield": "Yield %% = Credito / Capital em Risco ((N2-N1)*K2).",
                    "yield_cdi": "x CDI = Yield%% / CDI_do_periodo. >1x = bate o CDI no periodo.",
                    "protecao_pct": "Queda %% ate o BE = (Spot-BE)/Spot. Quanto maior, mais seguro.",
                    "be_down": "Breakeven inferior — abaixo deste preco a operacao fica no prejuizo.",
                    "pop_pct": "Probabilidade de Lucro = N(sigma_be)*100. Estimativa da chance do BE segurar.",
                    "perfil": "═══ Credito garantido (S>K1) | ╲ Tenda com lucro parcial (BE<S<K1) | __ Prejuizo (S<BE).",
                    "score": "Score = alpha*Prot%% + beta*MaxProfit/Spot + gamma*Credito/Spot.",
                    "zona": "Zona de confianca: A=sigma>=2 (alta), B=sigma>=1.5 (media), C (baixa).",
                    "dias": "Dias corridos ate o vencimento das opcoes.",
                    "vencimento": "Data de expiracao das opcoes.",
                    "cod_put_k1": "Codigo B3 da Put K1 (comprada). Ex: PETRH300.",
                    "cod_put_k2": "Codigo B3 da Put K2 (vendida). Ex: PETRH285.",
                    "iv_put_pct": "IV media das Puts (estimada via Newton-Raphson). Cap em 100%% no sigma_be.",
                    "iv_rank": "IV Rank 0-100 = (IV_atual - min_252d) / (max_252d - min_252d). >50 = volatilidade acima da media historica.",
                    "iv_percentile": "Percentil da IV atual na serie 252d. Ex: 80 = IV maior que 80%% dos dias.",
                    "qtd_ask_put_k1": "Volume no Ask da Put K1. Deve >= qtd_min para ser viavel.",
                    "qtd_bid_put_k2": "Volume no Bid da Put K2. Deve >= qtd_min para ser viavel.",
                    "label_detectado": "Data e hora da deteccao pelo monitor.",
                }
                return tips.get(PUT_RATIO_COLUMNS[section][1])
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = PUT_RATIO_COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            val = item.get(col_key)
            if val is None:
                return "-"
            if col_key in ("strike_k1", "strike_k2", "ask_put_k1", "bid_put_k2",
                           "credito_bruto", "be_down", "spot"):
                return "R$ {:.2f}".format(val)
            if col_key == "credit_yield":
                return "{:.2f}%".format(val * 100)
            if col_key == "yield_cdi":
                return "{:.2f}x".format(val)
            if col_key == "protecao_pct":
                return "{:.1f}%".format(val * 100)
            if col_key == "pop_pct":
                return "{:.1f}%".format(val)
            if col_key == "score":
                return "{:.1f}".format(val)
            if col_key == "iv_put_pct":
                return "{:.1f}%".format(val)
            if col_key in ("iv_rank", "iv_percentile"):
                return "{:.1f}".format(val) if val else "-"
            if col_key == "vencimento":
                if hasattr(val, "strftime"):
                    return val.strftime("%d/%m/%Y")
                return str(val)
            if col_key == "perfil":
                if isinstance(val, tuple):
                    p_loss, p_slope, p_credit = val
                    return f"__ {p_loss:.0f}% | ╲ {p_slope:.0f}% | ═══ {p_credit:.0f}%"
                return str(val) if val else "-"
            return str(val)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "score":
                val = item.get(col_key, 0)
                if val >= 5:
                    return QBrush(QColor(Palette.GREEN))
                if val >= 2:
                    return QBrush(QColor(Palette.YELLOW))
                return QBrush(QColor(Palette.TEXT_MUTED))
            if col_key == "zona":
                val = item.get(col_key, "")
                if val == "A":
                    return QBrush(QColor(Palette.GREEN))
                if val == "B":
                    return QBrush(QColor(Palette.YELLOW))
                return QBrush(QColor(Palette.RED))
            if col_key == "pop_pct":
                val = item.get(col_key, 0)
                if val >= 95:
                    return QBrush(QColor(Palette.GREEN))
                if val >= 85:
                    return QBrush(QColor(Palette.YELLOW))
                return QBrush(QColor(Palette.RED))
            if col_key in ("credito_bruto", "credit_yield", "yield_cdi", "protecao_pct"):
                val = item.get(col_key, 0)
                if val > 0:
                    return QBrush(QColor(Palette.GREEN))
                if val < 0:
                    return QBrush(QColor(Palette.RED))
            if col_key == "be_down":
                return QBrush(QColor(Palette.RED))
            if col_key in ("qtd_ask_put_k1", "qtd_bid_put_k2"):
                val = item.get(col_key, 0)
                if val <= 0:
                    return QBrush(QColor(Palette.RED))
                return QBrush(QColor(Palette.TEXT_PRIMARY))
            if col_key == "iv_rank":
                val = item.get(col_key, 0)
                if val >= 70:
                    return QBrush(QColor(Palette.GREEN))
                if val >= 40:
                    return QBrush(QColor(Palette.YELLOW))
                if val > 0:
                    return QBrush(QColor(Palette.RED))
            return QBrush(QColor(Palette.TEXT_MUTED))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            center_cols = {"strike_k1", "strike_k2", "ask_put_k1", "bid_put_k2",
                           "credito_bruto", "max_profit", "be_down",
                           "pct_cdi", "pct_cdi_liquido", "capital_margem",
                           "iv_put_pct", "iv_rank", "iv_percentile", "dias",
                           "qtd_ask_put_k1", "qtd_bid_put_k2",
                           "pop_pct", "ratio_label"}
            if col_key in center_cols:
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.BackgroundRole:
            if not item.get("viavel", False):
                return QBrush(QColor(Palette.ROW_NOT_VIABLE))
            return None

        return None

    def atualizar(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class PutRatioSortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cdi_min = 0.0
        self._only_viaveis = False

    def set_filtro_cdi_min(self, valor: float):
        self._cdi_min = valor
        self.invalidate()

    def set_filtro_viaveis(self, valor: bool):
        self._only_viaveis = valor
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        src = self.sourceModel()
        if self._cdi_min > 0:
            col_cdi = next((i for i, (_, k) in enumerate(PUT_RATIO_COLUMNS) if k == "yield_cdi"), -1)
            if col_cdi >= 0:
                val = src.data(src.index(row, col_cdi), Qt.ItemDataRole.DisplayRole) or "0.00x"
                try:
                    num = float(val.replace("x", "").strip())
                    if num < self._cdi_min:
                        return False
                except ValueError:
                    pass
        if self._only_viaveis:
            if not src._items[row].get("viavel", False):
                return False
        return True


class PutRatioDialog(QDialog):
    atualizar_put_ratio_signal = Signal(list)
    iniciar_scan_signal = Signal()
    parar_scan_signal = Signal()

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("📉 Put Ratio Spread")
        self.setMinimumSize(1100, 500)
        self._resultados = []
        self._pending_resultados = []
        self._update_pending = False
        self._scanning = False
        self._som_ativado = False
        self._db_path = db_path
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        lbl_title = QLabel("Put Ratio Spread")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        header.addWidget(lbl_title)
        header.addStretch()

        self.lbl_status = QLabel("Buscando...")
        self.lbl_status.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        header.addWidget(self.lbl_status)

        self.lbl_viaveis = QLabel("0 viaveis")
        self.lbl_viaveis.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; padding: 0 8px;".format(Palette.YELLOW))
        header.addWidget(self.lbl_viaveis)

        self.btn_scan = QPushButton("🔍 Iniciar Scanner")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #2d6a4f; color: #d8f3dc;
                border: none; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #40916c; }
        """)
        self.btn_scan.clicked.connect(self._toggle_scan)
        header.addWidget(self.btn_scan)

        self.btn_export_csv = QPushButton("📥 Export CSV")
        self.btn_export_csv.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8be08b;
                border: 1px solid #8be08b66; border-radius: 4px;
                padding: 4px 10px; font-size: 9pt;
            }
            QPushButton:hover { background-color: #8be08b22; }
        """)
        self.btn_export_csv.clicked.connect(self._exportar_csv)
        header.addWidget(self.btn_export_csv)

        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(10)

        left = QWidget()
        left.setFixedWidth(160)
        left_panel = QVBoxLayout(left)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(6)

        lbl_cdi = QLabel("Filtrar >= (x CDI):")
        lbl_cdi.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        left_panel.addWidget(lbl_cdi)

        self.spin_cdi_min = QDoubleSpinBox()
        self.spin_cdi_min.setRange(0.0, 999.0)
        self.spin_cdi_min.setValue(0.0)
        self.spin_cdi_min.setSingleStep(0.1)
        self.spin_cdi_min.setDecimals(1)
        self.spin_cdi_min.setSuffix("x CDI")
        self.spin_cdi_min.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 4px;
                padding: 4px; font-size: 9pt;
            }
            QDoubleSpinBox:focus { border-color: #2d6a4f; }
        """)
        self.spin_cdi_min.valueChanged.connect(self._on_filtro_cdi)
        left_panel.addWidget(self.spin_cdi_min)

        self._chk_apenas_viaveis = QCheckBox("Apenas viaveis")
        self._chk_apenas_viaveis.setToolTip(
            "Quando ativado, mostra apenas operacoes com credito > 0 "
            "e pct_cdi >= put_ratio_premio_risco."
        )
        self._chk_apenas_viaveis.setStyleSheet(
            "color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_PRIMARY)
        )
        self._chk_apenas_viaveis.toggled.connect(self._on_filtro_viaveis)
        left_panel.addWidget(self._chk_apenas_viaveis)

        left_panel.addStretch()
        body.addWidget(left)

        self.model = PutRatioTableModel()
        self.proxy = PutRatioSortProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.proxy.sort(12, Qt.DescendingOrder)  # Score column

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 8))
        header_h = self.table_view.horizontalHeader()
        header_h.setStretchLastSection(True)
        header_h.setSectionsMovable(True)
        header_h.setDragEnabled(True)
        header_h.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header_h, "put_ratio_table_order")))
        header_h.sectionResized.connect(lambda: QTimer.singleShot(0, lambda: salvar_largura_colunas(header_h, "put_ratio_table_width")))
        limpar_e_restaurar_colunas(header_h, "put_ratio_table_order", "put_ratio_table_width")
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.verticalHeader().hide()

        for i in range(self.model.columnCount()):
            header_h.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        col_perfil = next((i for i, (_, k) in enumerate(PUT_RATIO_COLUMNS) if k == "perfil"), -1)
        if col_perfil >= 0:
            self.table_view.setItemDelegateForColumn(col_perfil, _PerfilDelegate(self))

        self.table_view.doubleClicked.connect(self._on_row_double_clicked)

        body.addWidget(self.table_view, stretch=1)
        layout.addLayout(body)

        self._footer = QFrame()
        self._footer.setFrameShape(QFrame.StyledPanel)
        self._footer.setStyleSheet("background-color: #141428; border: 1px solid #2a2a44; border-radius: 6px; padding: 4px;")
        self._footer_layout = QHBoxLayout(self._footer)
        self._footer_layout.setContentsMargins(8, 4, 8, 4)
        self._footer_layout.setSpacing(8)
        lbl_dash = QLabel("📊 Series:")
        lbl_dash.setStyleSheet("color: #8888cc; font-size: 8pt; font-weight: bold; background: transparent; border: none;")
        self._footer_layout.addWidget(lbl_dash)
        self._footer_layout.addStretch()
        layout.addWidget(self._footer)

    def _exportar_csv(self):
        from src.ui.desktop.copy_utils import exportar_monitor_csv
        exportar_monitor_csv(
            resultados=self._resultados,
            colunas=PUT_RATIO_COLUMNS,
            table_view=self.table_view,
            parent=self,
            titulo_janela="Export CSV - Put Ratio",
        )

    def _toggle_scan(self):
        if self._scanning:
            self._scanning = False
            self.btn_scan.setText("🔍 Iniciar Scanner")
            self.lbl_status.setText("Scanner parado")
            self.parar_scan_signal.emit()
        else:
            self._scanning = True
            self.btn_scan.setText("⏹ Parar Scanner")
            self.lbl_status.setText("Buscando...")
            self.iniciar_scan_signal.emit()

    def _on_filtro_cdi(self, valor):
        self.proxy.set_filtro_cdi_min(valor)

    def _on_filtro_viaveis(self, checked):
        self.proxy.set_filtro_viaveis(checked)

    def atualizar_resultados(self, resultados: list):
        self._pending_resultados = resultados
        if not self._update_pending:
            self._update_pending = True
            QTimer.singleShot(0, self._processar_resultados)

    def _processar_resultados(self):
        self._update_pending = False
        resultados = self._pending_resultados
        self._resultados = resultados
        rows = []
        for r in resultados:
            rows.append({
                "ativo": r.ativo,
                "spot": getattr(r, 'spot', 0.0),
                "ratio_label": r.ratio_label,
                "strike_k1": r.strike_k1,
                "strike_k2": r.strike_k2,
                "ask_put_k1": r.ask_put_k1,
                "bid_put_k2": r.bid_put_k2,
                "credito_bruto": r.credito_bruto,
                "credit_yield": getattr(r, 'credit_yield', 0.0),
                "yield_cdi": getattr(r, 'yield_cdi', 0.0),
                "protecao_pct": getattr(r, 'protecao_pct', 0.0),
                "be_down": r.be_down,
                "pop_pct": getattr(r, 'pop_pct', 0.0),
                "score": getattr(r, 'score', 0.0),
                "zona": getattr(r, 'zona', ''),
                "perfil": _perfil_payoff(r),
                "dias": r.dias,
                "vencimento": r.vencimento,
                "cod_put_k1": r.cod_put_k1,
                "cod_put_k2": r.cod_put_k2,
                "iv_put_pct": r.iv_put_pct,
                "iv_rank": getattr(r, 'iv_rank', 0.0),
                "iv_percentile": getattr(r, 'iv_percentile', 0.0),
                "qtd_ask_put_k1": r.qtd_ask_put_k1,
                "qtd_bid_put_k2": r.qtd_bid_put_k2,
                "viavel": r.viavel,
                "label_detectado": _formatar_detectado(getattr(r, 'detectado_em', None)),
            })
        self.model.atualizar(rows)
        n = len(rows)
        viaveis = sum(1 for r in resultados if r.viavel)
        self.lbl_status.setText("{} puts ratio ({} viaveis)".format(n, viaveis))
        self.lbl_viaveis.setText("{} viaveis".format(viaveis))
        self._atualizar_dashboard(resultados)

    def _atualizar_dashboard(self, resultados):
        contagem: Counter = Counter()
        zonas: dict[str, list[float]] = {"A": [], "B": [], "C": []}
        for r in resultados:
            if r.viavel:
                key = r.vencimento.strftime("%d/%m/%y") if hasattr(r.vencimento, "strftime") else str(r.vencimento)
                contagem[key] += 1
            zona = getattr(r, 'zona', '')
            pop = getattr(r, 'pop_pct', 0.0)
            if zona in zonas:
                zonas[zona].append(pop)

        while self._footer_layout.count() > 2:
            item = self._footer_layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()

        for z in ("A", "B", "C"):
            pops = zonas[z]
            if pops:
                avg = sum(pops) / len(pops)
                badge = QLabel(f" Zona {z}  {len(pops)}  · POP {avg:.0f}% ")
                cores = {"A": ("#1e3a1e", "#4caf50"), "B": ("#3a351e", "#ffc107"), "C": ("#3a1e1e", "#ef5350")}
                bg, fg = cores.get(z, ("#222", "#aaa"))
                badge.setStyleSheet(f"""
                    QLabel {{
                        background-color: {bg}; color: {fg};
                        border: 1px solid {fg}44; border-radius: 4px;
                        padding: 2px 6px; font-size: 8pt; font-weight: bold;
                    }}
                """)
                self._footer_layout.insertWidget(self._footer_layout.count() - 1, badge)

        for data, qtd in sorted(contagem.items()):
            badge = QLabel(f" {data}  {qtd} ")
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: #1e3a1e; color: #4caf50;
                    border: 1px solid #2e5a2e; border-radius: 4px;
                    padding: 2px 6px; font-size: 8pt; font-weight: bold;
                }}
            """)
            self._footer_layout.insertWidget(self._footer_layout.count() - 1, badge)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self._abrir_pipeline()
        else:
            super().keyPressEvent(event)

    def _abrir_pipeline(self):
        from src.ui.desktop.pipeline_dialog import PipelineDialog
        tracker = None
        parent = self.parent()
        if parent and hasattr(parent, '_worker') and hasattr(parent._worker, '_monitor_put_ratio_uc'):
            tracker = getattr(parent._worker._monitor_put_ratio_uc, '_ultimo_pipeline', None)
        dlg = PipelineDialog(tracker, self)
        dlg.exec_()

    def _on_row_double_clicked(self, index):
        proxy_idx = self.proxy.mapToSource(index)
        row = proxy_idx.row()
        if row < 0 or row >= len(getattr(self, "_resultados", [])):
            return
        r = self._resultados[row]
        self._plot_payoff(r)

    def _plot_payoff(self, r):
        import numpy as np
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        K1 = r.strike_k1
        K2 = r.strike_k2
        N1 = r.n1
        N2 = r.n2
        credito = r.credito_bruto
        be = r.be_down
        lucro_max = r.max_profit

        x_min = K2 * 0.85
        x_max = K1 * 1.20
        x = np.linspace(x_min, x_max, 500)

        payoff = credito + N1 * np.maximum(K1 - x, 0) - N2 * np.maximum(K2 - x, 0)

        BG = '#0d0d0d'; GREEN = '#4caf50'; RED = '#ff3355'; BLUE = '#42a5f5'
        YELLOW = '#ffc107'; WHITE = '#ffffff'; TEXT = '#c0c0c0'

        fig = Figure(figsize=(8, 4.5), facecolor=BG)
        ax = fig.add_subplot(111, facecolor=BG)

        for i in range(len(x) - 1):
            mid = (payoff[i] + payoff[i + 1]) / 2
            cor = GREEN if mid >= 0 else RED
            ax.plot(x[i:i + 2], payoff[i:i + 2], color=cor, linewidth=2.5)

        ax.axhline(0, color=TEXT, linewidth=0.5, linestyle='--', alpha=0.4)
        ax.axvline(r.spot, color=WHITE, linewidth=1.2, linestyle='-', alpha=0.8, label=f'Spot=R$ {r.spot:.2f}')
        ax.axvline(be, color=RED, linewidth=1.0, linestyle='--', alpha=0.7, label=f'BE=R$ {be:.2f}')
        ax.axvline(K1, color=BLUE, linewidth=0.8, linestyle=':', alpha=0.6, label=f'K1=R$ {K1:.2f}')
        ax.axvline(K2, color=YELLOW, linewidth=0.8, linestyle=':', alpha=0.6, label=f'K2=R$ {K2:.2f}')

        zona_label = getattr(r, 'zona', '?')
        pop_val = getattr(r, 'pop_pct', 0.0)
        sigma = getattr(r, 'sigma_be', 0.0)
        iv = getattr(r, 'iv_put_pct', 0.0) / 100.0 if getattr(r, 'iv_put_pct', 0.0) > 0 else 0.0
        T_val = r.dias / 365.0
        spot_val = r.spot
        title = (f'{r.ativo} — Put Ratio {r.ratio_label} ({r.vencimento})  '
                 f'[Zona {zona_label} · {sigma:.1f}σ · POP {pop_val:.1f}%]')
        ax.set_title(title, color=WHITE, fontsize=11, fontweight='bold')

        if iv > 0 and spot_val > 0:
            s1 = spot_val * iv * math.sqrt(T_val)
            for n_sig, color_s, alpha_s, ls in [(1, '#336699', 0.3, '--'), (2, '#335577', 0.2, ':')]:
                up = spot_val + n_sig * s1
                lo = spot_val - n_sig * s1
                ax.axvline(up, color=color_s, linewidth=0.6, linestyle=ls, alpha=alpha_s)
                ax.axvline(lo, color=color_s, linewidth=0.6, linestyle=ls, alpha=alpha_s)
                if x_min <= up <= x_max:
                    ax.text(up, ax.get_ylim()[1] * 0.92, f'+{n_sig}σ', color=color_s, fontsize=7, ha='center', alpha=0.7)
                if x_min <= lo <= x_max:
                    ax.text(lo, ax.get_ylim()[1] * 0.92, f'-{n_sig}σ', color=color_s, fontsize=7, ha='center', alpha=0.7)
        ax.set_xlabel('Preco do Ativo no Vencimento (R$)', color=TEXT, fontsize=9)
        ax.set_ylabel('Lucro/Prejuizo (R$)', color=TEXT, fontsize=9)
        ax.tick_params(colors=TEXT, labelsize=8)
        ax.spines['bottom'].set_color('#333'); ax.spines['left'].set_color('#333')
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.legend(fontsize=8, facecolor=BG, edgecolor='#333', labelcolor=TEXT)
        ax.grid(True, alpha=0.08, color='white')
        fig.tight_layout()

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet(f"background-color: {BG};")

        payoff_dialog = QDialog(self, Qt.Window)
        payoff_dialog.setWindowTitle(f"Payoff — {r.ativo} Put Ratio {r.ratio_label}")
        payoff_dialog.setMinimumSize(750, 450)
        payoff_layout = QVBoxLayout(payoff_dialog)
        payoff_layout.setContentsMargins(8, 8, 8, 8)
        payoff_layout.addWidget(canvas)

        K1_cod = r.cod_put_k1
        K2_cod = r.cod_put_k2
        askK1 = r.ask_put_k1
        bidK2 = r.bid_put_k2
        qK1 = r.qtd_ask_put_k1
        qK2 = r.qtd_bid_put_k2
        ratio = r.ratio_label
        n1, n2 = r.n1, r.n2
        pop = getattr(r, 'pop_pct', 0.0)

        footer_ops = QLabel(
            f"<span style='color:{BLUE};'>{K1_cod}</span>"
            f"<span style='color:{TEXT};'> K1={K1:.2f} Ask={askK1:.2f} Q={qK1}</span>"
            f"<span style='color:{TEXT};'>  |  </span>"
            f"<span style='color:{YELLOW};'>{K2_cod}</span>"
            f"<span style='color:{TEXT};'> K2={K2:.2f} Bid={bidK2:.2f} Q={qK2}</span>"
        )
        footer_ops.setStyleSheet("font-family: Consolas; font-size: 9pt; padding: 2px;")

        footer_line2 = QLabel(
            f"<span style='color:{TEXT};'>Compra {n1}x {K1_cod}</span>"
            f"<span style='color:{TEXT};'>  |  Vende {n2}x {K2_cod}</span>"
            f"<span style='color:{TEXT};'>  |  </span>"
            f"<span style='color:{YELLOW};'>Credito: R$ {credito:.2f}</span>"
            f"<span style='color:{TEXT};'>  |  </span>"
            f"<span style='color:{GREEN};'>Lucro Max: R$ {lucro_max:.2f}</span>"
            f"<span style='color:{TEXT};'>  |  </span>"
            f"<span style='color:{RED};'>BE: R$ {be:.2f}</span>"
            f"<span style='color:{TEXT};'>  |  </span>"
            f"<span style='color:{TEXT};'>POP: {pop:.1f}%</span>"
            f"<span style='color:{TEXT};'>  |  CDI: {getattr(r, 'yield_cdi', 0):.2f}x</span>"
        )
        footer_line2.setStyleSheet("font-family: Consolas; font-size: 9pt; padding: 2px;")

        payoff_layout.addWidget(footer_ops)
        payoff_layout.addWidget(footer_line2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.setAutoDefault(False)
        btn_close.clicked.connect(payoff_dialog.close)
        btn_row.addWidget(btn_close)
        payoff_layout.addLayout(btn_row)
        payoff_dialog.exec_()

    def closeEvent(self, event):
        self.parar_scan_signal.emit()
        super().closeEvent(event)
