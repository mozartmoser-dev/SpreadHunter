from collections import Counter

from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal, QUrl
from PySide6.QtGui import QFont, QColor, QBrush, QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QFrame, QWidget,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QCheckBox,
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
    ("Score", "score"),
    ("Dias", "dias"),
    ("Venc", "vencimento"),
    ("Put K1", "cod_put_k1"),
    ("Put K2", "cod_put_k2"),
    ("IV PUT", "iv_put_pct"),
    ("Q K1", "qtd_ask_put_k1"),
    ("Q K2", "qtd_bid_put_k2"),
    ("Detectado", "label_detectado"),
]


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
                    "spot": "Preco atual do ativo (spot).",
                    "ratio_label": "Proporcao de Puts compradas x vendidas (ex: 1x2).",
                    "strike_k1": "Strike da Put comprada (ATM/OTM proximo).",
                    "strike_k2": "Strike da Put vendida (mais OTM).",
                    "ask_put_k1": "Preco de compra da Put K1 (Ask).",
                    "bid_put_k2": "Preco de venda da Put K2 (Bid).",
                    "credito_bruto": "Credito liquido recebido na montagem (N2*Bid_K2 - N1*Ask_K1).",
                    "credit_yield": "Rentabilidade: credito / capital em risco (N2-N1)*K2.",
                    "yield_cdi": "Quantas vezes o CDI do periodo o yield representa.",
                    "protecao_pct": "Queda %% suportada ate o breakeven (Spot-BE)/Spot.",
                    "max_profit": "Lucro maximo se o spot fechar exatamente em K2.",
                    "be_down": "Breakeven inferior — abaixo disso entra em prejuizo.",
                    "score": "Score combinado = Protecao%% * Yield * 10000 (ranking).",
                    "dias": "Dias corridos ate o vencimento.",
                    "vencimento": "Data de expiracao das opcoes.",
                    "cod_put_k1": "Codigo da Put K1.",
                    "cod_put_k2": "Codigo da Put K2.",
                    "iv_put_pct": "Volatilidade Implicita da Put K1 (%%).",
                    "qtd_ask_put_k1": "Quantidade no Ask da Put K1.",
                    "qtd_bid_put_k2": "Quantidade no Bid da Put K2.",
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
            if col_key == "score":
                return "{:.1f}".format(val)
            if col_key == "iv_put_pct":
                return "{:.1f}%".format(val)
            if col_key == "vencimento":
                if hasattr(val, "strftime"):
                    return val.strftime("%d/%m/%Y")
                return str(val)
            return str(val)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "score":
                val = item.get(col_key, 0)
                if val >= 5:
                    return QBrush(QColor(Palette.GREEN))
                if val >= 2:
                    return QBrush(QColor(Palette.YELLOW))
                return QBrush(QColor(Palette.TEXT_MUTED))
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
            return QBrush(QColor(Palette.TEXT_MUTED))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            center_cols = {"strike_k1", "strike_k2", "ask_put_k1", "bid_put_k2",
                           "credito_bruto", "max_profit", "be_down",
                           "pct_cdi", "pct_cdi_liquido", "capital_margem",
                           "iv_put_pct", "dias", "qtd_ask_put_k1", "qtd_bid_put_k2",
                           "ratio_label"}
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
                "score": getattr(r, 'score', 0.0),
                "dias": r.dias,
                "vencimento": r.vencimento,
                "cod_put_k1": r.cod_put_k1,
                "cod_put_k2": r.cod_put_k2,
                "iv_put_pct": r.iv_put_pct,
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
        for r in resultados:
            if r.viavel:
                key = r.vencimento.strftime("%d/%m/%y") if hasattr(r.vencimento, "strftime") else str(r.vencimento)
                contagem[key] += 1

        while self._footer_layout.count() > 2:
            item = self._footer_layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()

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
        x_max = K1 * 1.15
        x = np.linspace(x_min, x_max, 500)

        payoff = np.where(x >= K1, credito,
                 np.where(x >= K2, N1 * (K1 - x) + N2 * (x - K2) + credito,
                 np.where(x >= be, N1 * (K1 - x) + N2 * (x - K2) + credito,
                 N1 * (K1 - x) + N2 * (x - K2) + credito)))

        payoff = np.where(x >= K1, credito,
                 np.where(x >= K2, N1 * (K1 - K2) + credito - (N1 - N2) * (x - K2) + credito - credito,
                 # Simplified: at x, short puts = max(K2-x,0), long puts = max(K1-x,0)
                 # payoff = N2 * max(K2-x,0) - N2*premio_k2 - N1*max(K1-x,0) + N1*premio_k1
                 #         = credito + N2*max(K2-x,0) - N1*max(K1-x,0)
                 # Let me recalculate with option intrinsic values
                 np.maximum(K2 - x, 0) * N2 - np.maximum(K1 - x, 0) * N1 + credito))

        BG = '#0d0d0d'; GREEN = '#4caf50'; RED = '#ff3355'; BLUE = '#42a5f5'
        YELLOW = '#ffc107'; WHITE = '#ffffff'; TEXT = '#c0c0c0'

        fig = Figure(figsize=(8, 4.5), facecolor=BG)
        ax = fig.add_subplot(111, facecolor=BG)

        for i in range(len(x) - 1):
            mid = (payoff[i] + payoff[i + 1]) / 2
            cor = GREEN if mid >= 0 else RED
            ax.plot(x[i:i + 2], payoff[i:i + 2], color=cor, linewidth=2.5)

        ax.axhline(0, color=TEXT, linewidth=0.5, linestyle='--', alpha=0.4)
        ax.axvline(K1, color=BLUE, linewidth=0.8, linestyle=':', alpha=0.6, label=f'K1={K1:.2f}')
        ax.axvline(K2, color=YELLOW, linewidth=0.8, linestyle=':', alpha=0.6, label=f'K2={K2:.2f}')
        ax.axvline(be, color=RED, linewidth=0.8, linestyle='--', alpha=0.5, label=f'BE={be:.2f}')

        ax.set_title(f'{r.ativo} — Put Ratio {r.ratio_label} ({r.vencimento})', color=WHITE, fontsize=11, fontweight='bold')
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

        footer = QLabel(
            f"<span style='color:{YELLOW};'>Credito: R$ {credito:.2f}</span>  |  "
            f"<span style='color:{GREEN};'>Lucro Max: R$ {lucro_max:.2f}</span>  |  "
            f"<span style='color:{RED};'>BE Down: R$ {be:.2f}</span>  |  "
            f"<span style='color:{TEXT};'>CDI: {r.pct_cdi:.2f}x</span>"
        )
        footer.setStyleSheet("font-family: Consolas; font-size: 10pt; padding: 4px;")
        payoff_layout.addWidget(footer)

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
