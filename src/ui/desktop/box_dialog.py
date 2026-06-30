import winsound

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QFrame, QWidget,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QBrush

from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas
from src.ui.desktop.theme import Palette

CUSTOS_DISCLOSURE = (
    "\n\n* Custos já incluem taxa B3 (emolumento 0,025% + liquidação 0,0275% por perna) "
    "e IR (15% sobre o lucro líquido)."
)


BOX_4P_COLUMNS = [
    ("Ativo", "ativo"),
    ("K1", "strike_k1"),
    ("K2", "strike_k2"),
    ("Dist", "distancia"),
    ("CLR", "clr"),
    ("Lucro", "lucro"),
    ("Lucro B3", "lucro_b3"),
    ("Lucro Líq", "lucro_final"),
    ("Lucro%", "lucro_pct"),
    ("x CDI", "pct_cdi"),
    ("Call K1", "cod_call_k1"),
    ("Put K1", "cod_put_k1"),
    ("Call K2", "cod_call_k2"),
    ("Put K2", "cod_put_k2"),
    ("Bid C1", "bid_call_k1"),
    ("Ask P1", "ask_put_k1"),
    ("Ask C2", "ask_call_k2"),
    ("Bid P2", "bid_put_k2"),
    ("Q C1", "qtd_bid_call_k1"),
    ("Q P1", "qtd_ask_put_k1"),
    ("Q C2", "qtd_ask_call_k2"),
    ("Q P2", "qtd_bid_put_k2"),
    ("Dias", "dias"),
    ("Venc", "vencimento"),
]


class BoxTableModel(QAbstractTableModel):
    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(BOX_4P_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(BOX_4P_COLUMNS):
            if role == Qt.ItemDataRole.DisplayRole:
                return BOX_4P_COLUMNS[section][0]
            if role == Qt.ItemDataRole.ToolTipRole:
                tips = {
                    "ativo": "Código da ação objeto (ex: PETR4).",
                    "strike_k1": "Strike mais próximo do preço atual (perna interna).",
                    "strike_k2": "Strike mais distante do preço atual (perna externa).",
                    "distancia": "Diferença entre os dois strikes (K2 − K1).",
                    "clr": "Crédito/Líquido da montagem. Positivo = crédito, negativo = débito.",
                    "lucro": "Resultado bruto projetado da estrutura." + CUSTOS_DISCLOSURE,
                    "lucro_b3": "Resultado após deduzir custos B3 (emolumento + liquidação)." + CUSTOS_DISCLOSURE,
                    "lucro_final": "Resultado líquido final (após B3 + IR de 15%)." + CUSTOS_DISCLOSURE,
                    "lucro_pct": "Retorno percentual sobre o capital empregado." + CUSTOS_DISCLOSURE,
                    "pct_cdi": "Rentabilidade comparada ao CDI do período." + CUSTOS_DISCLOSURE,
                    "cod_call_k1": "Código da CALL no strike K1.",
                    "cod_put_k1": "Código da PUT no strike K1.",
                    "cod_call_k2": "Código da CALL no strike K2.",
                    "cod_put_k2": "Código da PUT no strike K2.",
                    "bid_call_k1": "Oferta de compra da CALL K1 (maior bid disponível).",
                    "ask_put_k1": "Oferta de venda da PUT K1 (menor ask disponível).",
                    "ask_call_k2": "Oferta de venda da CALL K2 (menor ask disponível).",
                    "bid_put_k2": "Oferta de compra da PUT K2 (maior bid disponível).",
                    "qtd_bid_call_k1": "Quantidade de contratos no bid da CALL K1.",
                    "qtd_ask_put_k1": "Quantidade de contratos no ask da PUT K1.",
                    "qtd_ask_call_k2": "Quantidade de contratos no ask da CALL K2.",
                    "qtd_bid_put_k2": "Quantidade de contratos no bid da PUT K2.",
                    "dias": "Dias corridos até o vencimento.",
                    "vencimento": "Data de expiração das opções.",
                }
                return tips.get(BOX_4P_COLUMNS[section][1])
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = BOX_4P_COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            val = item.get(col_key)
            if val is None:
                return "-"
            if col_key in ("strike_k1", "strike_k2", "distancia", "clr", "lucro",
                          "lucro_b3", "lucro_final",
                          "bid_call_k1", "ask_put_k1", "ask_call_k2", "bid_put_k2"):
                return "R$ {:.2f}".format(val)
            if col_key == "lucro_pct":
                return "{:.2f}%".format(val * 100)
            if col_key == "pct_cdi":
                return "{:.2f}x".format(val)
            if col_key == "vencimento":
                if hasattr(val, "strftime"):
                    return val.strftime("%d/%m/%Y")
                return str(val)
            return str(val)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key in ("lucro", "lucro_b3", "lucro_final", "lucro_pct", "pct_cdi"):
                val = item.get(col_key, 0)
                if val > 0:
                    return QBrush(QColor(Palette.GREEN))
                if val < 0:
                    return QBrush(QColor(Palette.RED))
                return QBrush(QColor(Palette.TEXT_MUTED))
            if col_key in ("qtd_bid_call_k1", "qtd_ask_put_k1", "qtd_ask_call_k2", "qtd_bid_put_k2"):
                val = item.get(col_key, 0)
                if val <= 0:
                    return QBrush(QColor(Palette.RED))
                return QBrush(QColor(Palette.TEXT_PRIMARY))
            return QBrush(QColor(Palette.TEXT_MUTED))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            center_cols = {"strike_k1", "strike_k2", "distancia", "clr", "lucro",
                          "lucro_b3", "lucro_final",
                          "lucro_pct", "pct_cdi", "dias", "qtd_bid_call_k1", "qtd_ask_put_k1",
                          "qtd_ask_call_k2", "qtd_bid_put_k2",
                          "bid_call_k1", "ask_put_k1", "ask_call_k2", "bid_put_k2"}
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


class BoxSortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cdi_min = 0.0

    def set_filtro_cdi_min(self, valor: float):
        self._cdi_min = valor
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        src = self.sourceModel()
        if self._cdi_min > 0:
            idx_cdi = 7
            val = src.data(src.index(row, idx_cdi), Qt.ItemDataRole.DisplayRole) or "0.00x"
            try:
                num = float(val.replace("x", "").strip())
                if num < self._cdi_min:
                    return False
            except ValueError:
                pass
        return True


class BoxDialog(QDialog):
    atualizar_boxes_signal = Signal(list)
    iniciar_scan_signal = Signal()
    parar_scan_signal = Signal()

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("📦 Box Spread 4 Pontas")
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
        lbl_title = QLabel("Box Spread 4 Pontas")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        header.addWidget(lbl_title)
        header.addStretch()

        self.lbl_status = QLabel("Buscando...")
        self.lbl_status.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        header.addWidget(self.lbl_status)

        self.lbl_viaveis = QLabel("0 viáveis")
        self.lbl_viaveis.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; padding: 0 8px;".format(Palette.YELLOW))
        header.addWidget(self.lbl_viaveis)

        self.lbl_div_warn = QLabel("")
        self.lbl_div_warn.setStyleSheet(
            "color: {}; font-size: 9pt; font-weight: bold; padding: 0 4px;".format(Palette.RED)
        )
        self.lbl_div_warn.setVisible(False)
        header.addWidget(self.lbl_div_warn)

        self.btn_bell = QPushButton("🔔")
        self.btn_bell.setFixedSize(26, 24)
        self.btn_bell.setToolTip("Som: desligado (clique para ligar)")
        self.btn_bell.setCursor(Qt.PointingHandCursor)
        self.btn_bell.setCheckable(True)
        self.btn_bell.setStyleSheet("""
            QPushButton {
                background-color: #3d1a1a; color: #ef4444;
                border: 1px solid #ef4444; border-radius: 4px;
                font-size: 11pt; padding: 0;
            }
            QPushButton:hover { background-color: #5d2a2a; }
            QPushButton:checked {
                background-color: #1a3d1a; color: #22c55e;
                border: 1px solid #22c55e;
            }
            QPushButton:checked:hover { background-color: #2a5d2a; }
        """)
        self.btn_bell.toggled.connect(self._toggle_som)
        header.addWidget(self.btn_bell)

        self.btn_scan = QPushButton("🔍 Iniciar Scanner")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: #0d0d1a;
                border: none; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.btn_scan.clicked.connect(self._toggle_scan)
        header.addWidget(self.btn_scan)

        self.btn_regras = QPushButton("📋 Regras")
        self.btn_regras.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8b8be0;
                border: 1px solid #8b8be066; border-radius: 4px;
                padding: 4px 10px; font-size: 9pt;
            }
            QPushButton:hover { background-color: #8b8be022; }
        """)
        self.btn_regras.setVisible(False)
        self.btn_regras.clicked.connect(self._abrir_regras)
        header.addWidget(self.btn_regras)

        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(10)

        left = QWidget()
        left.setFixedWidth(160)
        left_panel = QVBoxLayout(left)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(6)

        lbl_cdi = QLabel("Filtrar ≥ (x CDI):")
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
            QDoubleSpinBox:focus { border-color: #e74c3c; }
        """)
        self.spin_cdi_min.valueChanged.connect(self._on_filtro_cdi)
        left_panel.addWidget(self.spin_cdi_min)

        left_panel.addStretch()

        body.addWidget(left)

        self.model = BoxTableModel()
        self.proxy = BoxSortProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.proxy.sort(7, Qt.DescendingOrder)

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
        header_h.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header_h, "box_table_order")))
        restaurar_ordem_colunas(header_h, "box_table_order")
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.verticalHeader().hide()
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)

        for i in range(self.model.columnCount()):
            header_h.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        body.addWidget(self.table_view, stretch=1)
        layout.addLayout(body)

    def _abrir_regras(self):
        from src.ui.desktop.regras_dialog import RegrasDialog
        dlg = RegrasDialog("BOX_4P", self._db_path, self)
        dlg.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self.btn_regras.setVisible(not self.btn_regras.isVisible())
        elif event.key() == Qt.Key_F and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self._abrir_pipeline()
        else:
            super().keyPressEvent(event)

    def _abrir_pipeline(self):
        from src.ui.desktop.pipeline_dialog import PipelineDialog
        tracker = None
        parent = self.parent()
        if parent and hasattr(parent, '_worker') and hasattr(parent._worker, '_monitor_box_uc'):
            tracker = getattr(parent._worker._monitor_box_uc, '_ultimo_pipeline', None)
        dlg = PipelineDialog(tracker, self)
        dlg.exec_()

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
                "strike_k1": r.strike_k1,
                "strike_k2": r.strike_k2,
                "distancia": r.distancia,
                "clr": r.clr,
                "lucro": r.lucro,
                "custo_b3": r.custo_b3,
                "custo_ir": r.custo_ir,
                "lucro_b3": r.lucro - r.custo_b3,
                "lucro_final": r.lucro - r.custo_b3 - r.custo_ir,
                "lucro_liquido": r.lucro_liquido,
                "lucro_pct": r.lucro_pct,
                "pct_cdi": r.pct_cdi,
                "pct_cdi_liquido": r.pct_cdi_liquido,
                "cod_call_k1": r.cod_call_k1,
                "cod_put_k1": r.cod_put_k1,
                "cod_call_k2": r.cod_call_k2,
                "cod_put_k2": r.cod_put_k2,
                "bid_call_k1": r.bid_call_k1,
                "ask_put_k1": r.ask_put_k1,
                "ask_call_k2": r.ask_call_k2,
                "bid_put_k2": r.bid_put_k2,
                "qtd_bid_call_k1": r.qtd_bid_call_k1,
                "qtd_ask_put_k1": r.qtd_ask_put_k1,
                "qtd_ask_call_k2": r.qtd_ask_call_k2,
                "qtd_bid_put_k2": r.qtd_bid_put_k2,
                "dias": r.dias,
                "vencimento": r.vencimento,
                "viavel": r.viavel,
            })
        self.model.atualizar(rows)
        n = len(rows)
        viaveis = sum(1 for r in resultados if r.viavel)
        self.lbl_status.setText("{} boxes ({} viáveis)".format(n, viaveis))
        self.lbl_viaveis.setText("{} viáveis".format(viaveis))

        if self._som_ativado and viaveis > 0:
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 150)

        self._verificar_ex_dividendo(resultados)

    def _verificar_ex_dividendo(self, resultados):
        """Alerta se algum ativo nos resultados está em dia ex de dividendo."""
        if not self._db_path:
            return
        try:
            from src.infrastructure.persistence.repositories.repositories import DividendoRepository
            from datetime import date

            ativos = list(set(r.ativo for r in resultados))
            div_repo = DividendoRepository(self._db_path)
            divs_hoje = div_repo.get_ex_hoje()
            divs_presentes = [d for d in divs_hoje if d["ativo"] in ativos]
            if divs_presentes:
                nomes = ", ".join(set(d["ativo"] for d in divs_presentes))
                self.lbl_div_warn.setText(f"⚠ {nomes} ex-div hoje — strike pode estar errado")
                self.lbl_div_warn.setVisible(True)
            else:
                self.lbl_div_warn.setVisible(False)
        except Exception:
            self.lbl_div_warn.setVisible(False)

    def _toggle_som(self, ativo: bool):
        self._som_ativado = ativo
        self.btn_bell.setToolTip("Som: ligado" if ativo else "Som: desligado")

    def _on_row_double_clicked(self, index):
        proxy_idx = self.proxy.mapToSource(index)
        row = proxy_idx.row()
        if row < 0 or row >= len(getattr(self, "_resultados", [])):
            return
        r = self._resultados[row]
        self._mostrar_detalhes(r)

    def _mostrar_detalhes(self, r):
        from src.domain.services.calculadora_box import ResultadoBox

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Detalhes Box 4P — {r.ativo}")
        dialog.setMinimumSize(520, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"<b>{r.ativo}</b> — Box Spread 4 Pontas")
        title.setStyleSheet(f"font-size: 13pt; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(8)
        label_style = f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;"
        value_style = f"color: {Palette.TEXT_PRIMARY}; font-size: 10pt; font-family: Consolas;"

        lbl = QLabel("Vencimento:")
        lbl.setStyleSheet(label_style)
        val = QLabel(r.vencimento.strftime("%d/%m/%Y") if hasattr(r.vencimento, "strftime") else str(r.vencimento))
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("Dias:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.dias} dias")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep2)

        lbl = QLabel("Perna 1 — Vender Call (K1):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.cod_call_k1} — Bid R$ {r.bid_call_k1:.2f} (Qtd {r.qtd_bid_call_k1})")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("Perna 2 — Comprar Put (K1):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.cod_put_k1} — Ask R$ {r.ask_put_k1:.2f} (Qtd {r.qtd_ask_put_k1})")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("Perna 3 — Comprar Call (K2):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.cod_call_k2} — Ask R$ {r.ask_call_k2:.2f} (Qtd {r.qtd_ask_call_k2})")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("Perna 4 — Vender Put (K2):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.cod_put_k2} — Bid R$ {r.bid_put_k2:.2f} (Qtd {r.qtd_bid_put_k2})")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep3)

        lbl = QLabel("K1:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {r.strike_k1:.2f}")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("K2:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {r.strike_k2:.2f}")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("Distância (K2−K1):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {r.distancia:.2f}")
        val.setStyleSheet(f"color: {Palette.YELLOW}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        sep4 = QFrame()
        sep4.setFrameShape(QFrame.HLine)
        sep4.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep4)

        lbl = QLabel("CLR (Crédito Líquido):")
        lbl.setStyleSheet(label_style)
        clr_color = Palette.GREEN if r.clr > 0 else Palette.RED
        val = QLabel(f"R$ {r.clr:.2f}")
        val.setToolTip("Crédito Líquido Recebido = (Bid_Call_K1 + Bid_Put_K2) − (Ask_Put_K1 + Ask_Call_K2)" + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {clr_color}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("Lucro (CLR − Dist):")
        lbl.setStyleSheet(label_style)
        lucro_color = Palette.GREEN if r.lucro > 0 else Palette.RED
        val = QLabel(f"R$ {r.lucro:.2f}")
        val.setToolTip("Lucro bruto antes dos custos = CLR − Distância (K2−K1)" + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {lucro_color}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        pnl_b3 = r.lucro - r.custo_b3
        pnl_final = pnl_b3 - r.custo_ir

        lbl = QLabel("− Custos B3 (4 pernas):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"−R$ {r.custo_b3:.4f}")
        val.setToolTip("Taxas B3: emolumento (0,025%) + liquidação (0,0275%) × strike médio × 4 pernas.")
        val.setStyleSheet(f"color: {Palette.ORANGE}; font-size: 10pt; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("= Lucro pós-B3:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {pnl_b3:.2f}")
        val.setToolTip("Lucro após deduzir custos B3 (antes do IR)." + CUSTOS_DISCLOSURE)
        b3_color = Palette.GREEN if pnl_b3 > 0 else Palette.RED
        val.setStyleSheet(f"color: {b3_color}; font-size: 10pt; font-family: Consolas;")
        form.addRow(lbl, val)

        if r.custo_ir > 0:
            lbl = QLabel("− IR (15%):")
            lbl.setStyleSheet(label_style)
            val_ir = QLabel(f"−R$ {r.custo_ir:.4f}")
            val_ir.setToolTip("Imposto de Renda (15%) sobre o lucro líquido." + CUSTOS_DISCLOSURE)
            val_ir.setStyleSheet(f"color: {Palette.ORANGE}; font-size: 10pt; font-family: Consolas;")
            form.addRow(lbl, val_ir)

        lbl = QLabel("= Lucro Líquido:")
        lbl.setStyleSheet(label_style)
        liq_color = Palette.GREEN if pnl_final > 0 else Palette.RED
        val = QLabel(f"R$ {pnl_final:.2f}")
        val.setToolTip("Lucro líquido após descontar custos B3 e IR." + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {liq_color}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("Retorno líquido:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.lucro_pct*100:.2f}% / {r.pct_cdi:.2f}x CDI ({r.pct_cdi_liquido:.2f}x CDI líquido)")
        val.setToolTip(
            "Percentual de retorno e múltiplos do CDI (bruto e líquido de IR)."
            + CUSTOS_DISCLOSURE
        )
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        paga_cdi = r.pct_cdi_liquido >= 1.0
        lbl = QLabel("Status:")
        lbl.setStyleSheet(label_style)
        txt = "✅ Paga o CDI+" if paga_cdi else "❌ Paga abaixo do CDI"
        cor = Palette.GREEN if paga_cdi else Palette.RED
        val = QLabel(txt)
        val.setStyleSheet(f"color: {cor}; font-size: 10pt; font-weight: bold;")
        form.addRow(lbl, val)

        layout.addLayout(form)

        detalhes = QLabel(
            "<p style='color:{}; font-size:8pt;'>"
            "CLR = (Bid_Call_K1 + Bid_Put_K2) − (Ask_Put_K1 + Ask_Call_K2)<br>"
            "O box paga K2−K1 no vencimento. Lucro se CLR > K2−K1.</p>".format(Palette.TEXT_MUTED)
        )
        layout.addWidget(detalhes)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_pnt = QPushButton("📋 Basket PNT")
        btn_pnt.setAutoDefault(False)
        btn_pnt.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_pnt.clicked.connect(lambda: self._abrir_boleta_box(r))
        btn_row.addWidget(btn_pnt)

        btn_row.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)

        layout.addLayout(btn_row)
        dialog.exec_()

    def _abrir_boleta_box(self, r):
        from src.ui.desktop.boleta_dialog import BoletaDialog
        dlg = BoletaDialog("BOX 4P", r, self._db_path, self)
        dlg.exec_()

    def closeEvent(self, event):
        self.parar_scan_signal.emit()
        super().closeEvent(event)
