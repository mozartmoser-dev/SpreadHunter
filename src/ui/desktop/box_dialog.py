from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QFrame, QWidget,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QCheckBox,
)
from collections import Counter

from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal, QUrl
from PySide6.QtGui import QFont, QColor, QBrush, QDesktopServices

from src.ui.desktop.column_utils import salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas
from src.ui.desktop.flag_icons import flag_icon
from src.ui.desktop.theme import Palette

CUSTOS_DISCLOSURE = (
    "\n\n* Custos já incluem taxa B3 (emolumento 0,025% + liquidação 0,0275% por perna) "
    "e IR (15% sobre o lucro líquido)."
)

def _formatar_detectado(detectado_em):
    if detectado_em is None:
        return ""
    return detectado_em.strftime("%d/%m/%Y %H:%M:%S")


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
    ("BTC", "taxa_aluguel"),
    ("Cód.Call C.K1", "cod_call_k1"),
    ("Cód.Put V.K1", "cod_put_k1"),
    ("Cód.Call V.K2", "cod_call_k2"),
    ("Cód.Put C.K2", "cod_put_k2"),
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
    ("Detectado", "label_detectado"),
    ("Sentido", "sentido"),
    ("Mod", "tipo_opcao"),
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
                    "cod_call_k1": "Código da CALL comprada em K1.",
                    "cod_put_k1": "Código da PUT vendida em K1.",
                    "cod_call_k2": "Código da CALL vendida em K2.",
                    "cod_put_k2": "Código da PUT comprada em K2.",
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
                    "taxa_aluguel": "Taxa de aluguel (BTC) da ação objeto — InvestSite.",
                    "label_detectado": "Data e hora (Brasília) em que o monitor detectou a oportunidade pelo RTD (DD/MM/YYYY HH:MM:SS).",
                    "tipo_opcao": "MOD — estilo da opção (CALL K1): 🇺🇸 = Americana (A) | 🇪🇺 = Europeia (E).",
                    "sentido": "Sentido da operação: VENDIDO (short box) = recebe hoje, paga no vencimento | COMPRADO (long box) = paga hoje, recebe no vencimento.",
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
            if col_key == "taxa_aluguel":
                return "{:.2f}%".format(val)
            if col_key == "vencimento":
                if hasattr(val, "strftime"):
                    return val.strftime("%d/%m/%Y")
                return str(val)
            return str(val)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "sentido":
                val = item.get(col_key, "")
                if val == "COMPRADO":
                    return QBrush(QColor(Palette.GREEN))
                if val == "VENDIDO":
                    return QBrush(QColor(Palette.RED))
                return QBrush(QColor(Palette.TEXT_MUTED))
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
                           "bid_call_k1", "ask_put_k1", "ask_call_k2", "bid_put_k2",
                           "taxa_aluguel", "tipo_opcao", "sentido"}
            if col_key in center_cols:
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.BackgroundRole:
            if not item.get("viavel", False):
                return QBrush(QColor(Palette.ROW_NOT_VIABLE))
            return None

        if role == Qt.ItemDataRole.DecorationRole and col_key == "tipo_opcao":
            val = item.get(col_key, "")
            return flag_icon(val) if val else None

        return None

    def atualizar(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class BoxSortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cdi_min = 0.0
        self._sentido = ""
        self._mod = ""
        self._only_viaveis = False

    def set_filtro_cdi_min(self, valor: float):
        self._cdi_min = valor
        self.invalidate()

    def set_filtro_sentido(self, valor: str):
        self._sentido = valor
        self.invalidate()

    def set_filtro_mod(self, valor: str):
        self._mod = valor
        self.invalidate()

    def set_filtro_viaveis(self, valor: bool):
        self._only_viaveis = valor
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        src = self.sourceModel()
        if self._cdi_min > 0:
            idx_cdi = 9
            val = src.data(src.index(row, idx_cdi), Qt.ItemDataRole.DisplayRole) or "0.00x"
            try:
                num = float(val.replace("x", "").strip())
                if num < self._cdi_min:
                    return False
            except ValueError:
                pass
        if self._sentido:
            col_sentido = next((i for i, (_, k) in enumerate(BOX_4P_COLUMNS) if k == "sentido"), -1)
            if col_sentido >= 0:
                val = src.data(src.index(row, col_sentido), Qt.ItemDataRole.DisplayRole) or ""
                if val != self._sentido:
                    return False
        if self._mod:
            col_mod = next((i for i, (_, k) in enumerate(BOX_4P_COLUMNS) if k == "tipo_opcao"), -1)
            if col_mod >= 0:
                val = src.data(src.index(row, col_mod), Qt.ItemDataRole.DisplayRole) or ""
                if val != self._mod:
                    return False
        if self._only_viaveis:
            if not src._items[row].get("viavel", False):
                return False
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

        self.btn_export_csv = QPushButton("📥 Export CSV")
        self.btn_export_csv.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8be08b;
                border: 1px solid #8be08b66; border-radius: 4px;
                padding: 4px 10px; font-size: 9pt;
            }
            QPushButton:hover { background-color: #8be08b22; }
        """)
        self.btn_export_csv.setToolTip("Exporta a grade do BOX 4P para o clipboard em CSV.\nSe houver uma linha selecionada, exporta apenas ela; senao, todas.")
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

        lbl_sentido = QLabel("Sentido:")
        lbl_sentido.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; margin-top: 8px;".format(Palette.TEXT_MUTED))
        left_panel.addWidget(lbl_sentido)

        self._sentido_group = QButtonGroup(self)
        self._radio_todos = QRadioButton("Todos")
        self._radio_vendido = QRadioButton("Vendido")
        self._radio_comprado = QRadioButton("Comprado")
        for rb, style in [(self._radio_todos, Palette.TEXT_PRIMARY),
                          (self._radio_vendido, Palette.RED),
                          (self._radio_comprado, Palette.GREEN)]:
            rb.setStyleSheet("color: {}; font-size: 8pt;".format(style))
            self._sentido_group.addButton(rb)
            left_panel.addWidget(rb)
        self._radio_todos.setChecked(True)
        self._sentido_group.buttonClicked.connect(self._on_filtro_sentido)

        lbl_mod = QLabel("MOD:")
        lbl_mod.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; margin-top: 8px;".format(Palette.TEXT_MUTED))
        left_panel.addWidget(lbl_mod)

        self._mod_group = QButtonGroup(self)
        self._radio_mod_todos = QRadioButton("Todos")
        self._radio_mod_eu = QRadioButton(" Europeia")
        self._radio_mod_us = QRadioButton(" Americana")
        self._radio_mod_eu.setIcon(flag_icon("E"))
        self._radio_mod_us.setIcon(flag_icon("A"))
        for rb in [self._radio_mod_todos, self._radio_mod_eu, self._radio_mod_us]:
            rb.setStyleSheet("color: {}; font-size: 8pt;".format(Palette.TEXT_PRIMARY))
            self._mod_group.addButton(rb)
            left_panel.addWidget(rb)
        self._radio_mod_todos.setChecked(True)
        self._mod_group.buttonClicked.connect(self._on_filtro_mod)

        self._chk_apenas_viaveis = QCheckBox("Apenas viáveis")
        self._chk_apenas_viaveis.setToolTip(
            "Quando ativado, mostra apenas operações que superam o prêmio de risco "
            "configurado nos parâmetros (box_premio_risco).\n"
            "Viável = pct_cdi_bruto >= box_premio_risco, lucro líquido > 0 "
            "e profundidade mínima atendida."
        )
        self._chk_apenas_viaveis.setStyleSheet(
            "color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_PRIMARY)
        )
        self._chk_apenas_viaveis.toggled.connect(self._on_filtro_viaveis)
        left_panel.addWidget(self._chk_apenas_viaveis)

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
        header_h.sectionResized.connect(lambda: QTimer.singleShot(0, lambda: salvar_largura_colunas(header_h, "box_table_width")))
        limpar_e_restaurar_colunas(header_h, "box_table_order", "box_table_width")
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.verticalHeader().hide()
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.clicked.connect(self._on_btc_clicked)

        for i in range(self.model.columnCount()):
            header_h.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        body.addWidget(self.table_view, stretch=1)
        layout.addLayout(body)

        self._footer = QFrame()
        self._footer.setFrameShape(QFrame.StyledPanel)
        self._footer.setStyleSheet("background-color: #141428; border: 1px solid #2a2a44; border-radius: 6px; padding: 4px;")
        self._footer_layout = QHBoxLayout(self._footer)
        self._footer_layout.setContentsMargins(8, 4, 8, 4)
        self._footer_layout.setSpacing(8)
        lbl_dash = QLabel("📊 Séries:")
        lbl_dash.setStyleSheet("color: #8888cc; font-size: 8pt; font-weight: bold; background: transparent; border: none;")
        self._footer_layout.addWidget(lbl_dash)
        self._footer_layout.addStretch()
        layout.addWidget(self._footer)

    def _exportar_csv(self):
        from src.ui.desktop.copy_utils import exportar_monitor_csv
        exportar_monitor_csv(
            resultados=self._resultados,
            colunas=BOX_4P_COLUMNS,
            table_view=self.table_view,
            parent=self,
            titulo_janela="Export CSV - BOX 4P",
        )

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

    def _on_filtro_sentido(self, btn):
        if btn is self._radio_vendido:
            self.proxy.set_filtro_sentido("VENDIDO")
        elif btn is self._radio_comprado:
            self.proxy.set_filtro_sentido("COMPRADO")
        else:
            self.proxy.set_filtro_sentido("")

    def _on_filtro_mod(self, btn):
        if btn is self._radio_mod_eu:
            self.proxy.set_filtro_mod("E")
        elif btn is self._radio_mod_us:
            self.proxy.set_filtro_mod("A")
        else:
            self.proxy.set_filtro_mod("")

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
                "taxa_aluguel": r.taxa_aluguel,
                "viavel": r.viavel,
                "tipo_opcao": getattr(r, 'tipo_opcao', '') or '',
                "sentido": getattr(r, 'sentido', 'VENDIDO') or 'VENDIDO',
                "label_detectado": _formatar_detectado(getattr(r, 'detectado_em', None)),
            })
        self.model.atualizar(rows)
        n = len(rows)
        viaveis = sum(1 for r in resultados if r.viavel)
        self.lbl_status.setText("{} boxes ({} viáveis)".format(n, viaveis))
        self.lbl_viaveis.setText("{} viáveis".format(viaveis))
        self._atualizar_dashboard(resultados)

        if self._som_ativado and viaveis > 0:
            from src.infrastructure.services.som_service import tocar
            tocar(self._db_path)

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

    def _on_btc_clicked(self, index):
        if index.column() != self._coluna_btc():
            return
        proxy_idx = self.proxy.mapToSource(index)
        row = proxy_idx.row()
        if row < 0 or row >= len(getattr(self, "_resultados", [])):
            return
        ativo = self._resultados[row].ativo
        url = QUrl(f"https://www.investsite.com.br/graficos_aluguel_registro.php?cod_negociacao={ativo}")
        QDesktopServices.openUrl(url)

    def _coluna_btc(self):
        for i, (_, key) in enumerate(BOX_4P_COLUMNS):
            if key == "taxa_aluguel":
                return i
        return -1

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
        dialog.setWindowTitle(f"Detalhes Box 4P — {r.ativo} ({r.sentido})")
        dialog.setMinimumSize(520, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        is_comprado = getattr(r, 'sentido', 'VENDIDO') == 'COMPRADO'

        title = QLabel(f"<b>{r.ativo}</b> — Box Spread 4 Pontas ({r.sentido})")
        title.setStyleSheet(f"font-size: 13pt; color: {Palette.GREEN if is_comprado else Palette.RED};")
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

        if is_comprado:
            lbl = QLabel("Perna 1 — Comprar Call (K1):")
            lbl.setStyleSheet(label_style)
            val = QLabel(f"{r.cod_call_k1} — Ask R$ {r.bid_call_k1:.2f} (Qtd {r.qtd_bid_call_k1})")
            val.setStyleSheet(value_style)
            form.addRow(lbl, val)

            lbl = QLabel("Perna 2 — Vender Put (K1):")
            lbl.setStyleSheet(label_style)
            val = QLabel(f"{r.cod_put_k1} — Bid R$ {r.ask_put_k1:.2f} (Qtd {r.qtd_ask_put_k1})")
            val.setStyleSheet(value_style)
            form.addRow(lbl, val)

            lbl = QLabel("Perna 3 — Vender Call (K2):")
            lbl.setStyleSheet(label_style)
            val = QLabel(f"{r.cod_call_k2} — Bid R$ {r.ask_call_k2:.2f} (Qtd {r.qtd_ask_call_k2})")
            val.setStyleSheet(value_style)
            form.addRow(lbl, val)

            lbl = QLabel("Perna 4 — Comprar Put (K2):")
            lbl.setStyleSheet(label_style)
            val = QLabel(f"{r.cod_put_k2} — Ask R$ {r.bid_put_k2:.2f} (Qtd {r.qtd_bid_put_k2})")
            val.setStyleSheet(value_style)
            form.addRow(lbl, val)
        else:
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

        lbl = QLabel("CLR (Crédito Líquido):" if not is_comprado else "Débito (Custo da montagem):")
        lbl.setStyleSheet(label_style)
        clr_color = Palette.GREEN if r.clr > 0 else Palette.RED
        val = QLabel(f"R$ {r.clr:.2f}")
        val.setToolTip(
            "Crédito Líquido = (Bid_Call_K1 + Bid_Put_K2) − (Ask_Put_K1 + Ask_Call_K2)" if not is_comprado
            else "Débito = (Ask_Call_K1 + Ask_Put_K2) − (Bid_Put_K1 + Bid_Call_K2)" 
            + CUSTOS_DISCLOSURE
        )
        val.setStyleSheet(f"color: {clr_color}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("Lucro (CLR − Dist):" if not is_comprado else "Lucro (Dist − Débito):")
        lbl.setStyleSheet(label_style)
        lucro_color = Palette.GREEN if r.lucro > 0 else Palette.RED
        val = QLabel(f"R$ {r.lucro:.2f}")
        val.setToolTip(
            "Lucro bruto = CLR − Distância" if not is_comprado
            else "Lucro bruto = Distância − Débito"
            + CUSTOS_DISCLOSURE
        )
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

        if not is_comprado:
            detalhes = QLabel(
                "<p style='color:{}; font-size:8pt;'>"
                "CLR = (Bid_Call_K1 + Bid_Put_K2) − (Ask_Put_K1 + Ask_Call_K2)<br>"
                "O box paga K2−K1 no vencimento. Lucro se CLR > K2−K1.</p>".format(Palette.TEXT_MUTED)
            )
        else:
            detalhes = QLabel(
                "<p style='color:{}; font-size:8pt;'>"
                "Débito = (Ask_Call_K1 + Ask_Put_K2) − (Bid_Put_K1 + Bid_Call_K2)<br>"
                "O box recebe K2−K1 no vencimento. Lucro se Débito < K2−K1.</p>".format(Palette.TEXT_MUTED)
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
