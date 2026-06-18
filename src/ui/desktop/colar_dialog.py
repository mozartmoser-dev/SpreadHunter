from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QLineEdit, QFormLayout, QFrame,
    QListWidget, QListWidgetItem, QWidget, QTextEdit, QSpinBox,
)
import winsound

from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, QStringListModel, Signal
from PySide6.QtGui import QFont, QColor, QBrush

from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas
from src.ui.desktop.theme import Palette

CUSTOS_DISCLOSURE = (
    "\n\n* Custos já incluem taxa B3 (emolumento 0,025% + liquidação 0,0275% por perna) "
    "e IR (15% sobre o lucro líquido)."
)


WHITELIST_CHAVE_COLAR = "white_list_colar"


def ler_whitelist_colar(db_path: str | None = None) -> list[str]:
    from src.infrastructure.persistence.repositories.repositories import ParametroRepository
    repo = ParametroRepository(db_path)
    param = repo.get_by_chave(WHITELIST_CHAVE_COLAR)
    if param and param.valor:
        raw = str(param.valor)
        return [a.strip().upper() for a in raw.split(",") if a.strip()]
    return []


CLASSIF_CORES = {
    "Viés Neutro": QColor("#1abc9c"),
    "Viés Baixa": QColor("#9b59b6"),
    "Viés Alta": QColor("#e67e22"),
}

RISCO_CORES = {
    "Baixo": QBrush(QColor(Palette.GREEN)),
    "Médio": QBrush(QColor(Palette.ORANGE)),
    "Alto": QBrush(QColor(Palette.RED)),
}


class ColarTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Score", "score"),
        ("Pop ↑", "pop_upside"),
        ("Pop ↓", "pop_downside"),
        ("Pior%xCDI", "pct_cdi"),
        ("Melhor%xCDI", "pct_cdi_melhor"),
        ("Vencimento", "vencimento"),
        ("Tipo", "tipo_str"),
        ("K Put", "strike_put"),
        ("K Call", "strike_call"),
        ("Cód Put", "cod_put"),
        ("Cód Call", "cod_call"),
        ("Custo Liq", "custo_liquido"),
        ("Pior Ret", "pior_retorno"),
        ("Pior B3", "pior_b3"),
        ("Pior Líq", "pior_liquido"),
        ("Risco Desp.", "risco_str"),
        ("Dias", "dias"),
    ]

    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section][0]
            if role == Qt.ItemDataRole.ToolTipRole:
                tips = {
                    "ativo": "Código da ação objeto (ex: PETR4).",
                    "score": "Score de ranking multicritério (0–10+). "
                             "Fórmula: peso_pop × Pop_NORM + peso_cdi × CDI_NORM + peso_risco × RISCO.\n"
                             "• Pop_NORM = (100 − |Pop↑ − Pop↓|) ÷ max(Pop_BALANCEADA) no lote — penaliza skew\n"
                             "• CDI_NORM = pior%xCDI ÷ max(pior%xCDI) no lote\n"
                             "• RISCO = 1.0 (Baixo), 0.5 (Médio), 0.0 (Alto)\n"
                             "Ordem padrão: Score decrescente. Pesos configuráveis em Parâmetros > Colar Protetivo.",
                    "pop_upside": "Probabilidade de o ativo estar acima do strike CALL no vencimento.",
                    "pop_downside": "Probabilidade de o ativo estar abaixo do strike PUT no vencimento.",
                    "pct_cdi": "Retorno no pior cenário comparado ao CDI do período." + CUSTOS_DISCLOSURE,
                    "pct_cdi_melhor": "Retorno no melhor cenário comparado ao CDI do período." + CUSTOS_DISCLOSURE,
                    "vencimento": "Data de expiração das opções do colar.",
                    "tipo_str": "Classificação do viés: Neutro (Kp < S0 < Kc), Baixa (Kp e Kc abaixo), Alta (Kp e Kc acima).",
                    "strike_put": "Preço de exercício da PUT de proteção.",
                    "strike_call": "Preço de exercício da CALL vendida.",
                    "cod_put": "Código da PUT na B3.",
                    "cod_call": "Código da CALL na B3.",
                    "custo_liquido": "Custo total de montagem da estrutura (ação + PUT − CALL)." + CUSTOS_DISCLOSURE,
                    "pior_retorno": "Valor do pior resultado possível no vencimento." + CUSTOS_DISCLOSURE,
                    "pior_b3": "Valor do pior resultado após custos B3 (emolumento + liquidação)." + CUSTOS_DISCLOSURE,
                    "pior_liquido": "Valor do pior resultado líquido (após B3 + IR)." + CUSTOS_DISCLOSURE,
                    "risco_str": "Nível de risco de leilão baseado no volume das opções.",
                    "dias": "Dias corridos até o vencimento.",
                }
                return tips.get(self.COLUMNS[section][1])
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            val = item.get(col_key)
            if val is None:
                return "-"
            try:
                if col_key in ("strike_put", "strike_call", "custo_liquido", "pior_retorno",
                               "pior_b3", "pior_liquido"):
                    return "R$ {:.2f}".format(val)
                if col_key == "score":
                    return f"{val:.2f}"
                if col_key in ("pct_cdi", "pct_cdi_melhor"):
                    return "{:.2f}x".format(val)
                if col_key in ("pop_upside", "pop_downside"):
                    if val is None:
                        return "-"
                    return "{:.1f}%".format(val)
                if col_key == "vencimento":
                    if hasattr(val, "strftime"):
                        return val.strftime("%d/%m/%Y")
                    return str(val)
            except Exception:
                return str(val)
            return str(val)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "tipo_str":
                tipo = item.get("tipo_str", "")
                cor = CLASSIF_CORES.get(tipo)
                if cor:
                    return QBrush(cor)
                return QBrush(QColor(Palette.TEXT_PRIMARY))
            if col_key == "risco_str":
                risco = item.get("risco_str", "")
                return RISCO_CORES.get(risco, QBrush(QColor(Palette.TEXT_MUTED)))
            if col_key in ("pct_cdi", "pct_cdi_melhor", "score"):
                return QBrush(QColor(Palette.YELLOW))
            if col_key in ("strike_put", "strike_call", "custo_liquido", "pior_retorno"):
                return QBrush(QColor(Palette.TEXT_PRIMARY))
            if col_key in ("pior_b3", "pior_liquido"):
                val = item.get(col_key, 0)
                if val > 0:
                    return QBrush(QColor(Palette.GREEN))
                if val < 0:
                    return QBrush(QColor(Palette.RED))
                return QBrush(QColor(Palette.TEXT_MUTED))
            return QBrush(QColor(Palette.TEXT_MUTED))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            center_cols = {"score", "strike_put", "strike_call", "custo_liquido", "pior_retorno",
                           "pior_b3", "pior_liquido",
                           "pct_cdi", "pct_cdi_melhor", "pop_upside", "pop_downside",
                           "risco_str", "dias"}
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


class ColarSortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtro_ativo = ""
        self._filtro_lista = None
        self._pop_upside_min = 0.0
        self._pop_downside_min = 0.0
        self._top_n = 0
        self._top_n_accept_set: set[int] | None = None

    def set_filtro_ativo(self, texto: str):
        self._filtro_ativo = texto.strip().upper()
        self._filtro_lista = None
        self._top_n_accept_set = None
        self.invalidateFilter()

    def set_filtro_lista(self, ativos: set):
        self._filtro_lista = ativos
        self._filtro_ativo = ""
        self._top_n_accept_set = None
        self.invalidateFilter()

    def set_filtro_pop_upside(self, minimo: float):
        self._pop_upside_min = minimo
        self._top_n_accept_set = None
        self.invalidateFilter()

    def set_filtro_pop_downside(self, minimo: float):
        self._pop_downside_min = minimo
        self._top_n_accept_set = None
        self.invalidateFilter()

    def set_top_n(self, n: int):
        self._top_n = n
        self._top_n_accept_set = None
        self.invalidateFilter()

    def sort(self, column, order):
        super().sort(column, order)
        self._top_n_accept_set = None

    def _recompute_top_n(self):
        src = self.sourceModel()
        n = self._top_n
        sort_col = self.sortColumn()
        if sort_col < 0:
            sort_col = 3
        sort_order = self.sortOrder()

        rows_by_ativo: dict[str, list[int]] = {}
        for row in range(src.rowCount()):
            idx = src.index(row, 0)
            ativo = src.data(idx, Qt.ItemDataRole.DisplayRole) or ""
            rows_by_ativo.setdefault(ativo, []).append(row)

        accept: set[int] = set()
        for ativo, rows in rows_by_ativo.items():
            def _sort_key(r):
                idx = src.index(r, sort_col)
                raw = src.data(idx, Qt.ItemDataRole.DisplayRole) or "0"
                try:
                    return float(str(raw).replace("R$", "").replace("x", "").replace("%", "").replace(",", ".").strip())
                except Exception:
                    return 0.0
            sorted_rows = sorted(rows, key=_sort_key, reverse=(sort_order == Qt.DescendingOrder))
            accept.update(sorted_rows[:n])

        self._top_n_accept_set = accept

    def filterAcceptsRow(self, row, parent):
        src = self.sourceModel()
        idx = src.index(row, 0)
        ativo = src.data(idx, Qt.ItemDataRole.DisplayRole) or ""

        if self._filtro_lista is not None:
            if ativo not in self._filtro_lista:
                return False
        elif self._filtro_ativo:
            if self._filtro_ativo not in ativo.upper():
                return False

        if self._pop_upside_min > 0:
            col_upside = 1
            val = src.data(src.index(row, col_upside), Qt.ItemDataRole.DisplayRole) or "0%"
            try:
                if float(val.replace("%", "")) < self._pop_upside_min:
                    return False
            except ValueError:
                pass

        if self._pop_downside_min > 0:
            col_downside = 2
            val = src.data(src.index(row, col_downside), Qt.ItemDataRole.DisplayRole) or "0%"
            try:
                if float(val.replace("%", "")) < self._pop_downside_min:
                    return False
            except ValueError:
                pass

        if self._top_n > 0:
            if self._top_n_accept_set is None:
                self._recompute_top_n()
            if row not in self._top_n_accept_set:
                return False

        return True


class ColarDialog(QDialog):
    iniciar_scan_signal = Signal()
    parar_scan_signal = Signal()
    selecao_alterada = Signal(list)

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("🛡 Monitor de Colares Protetivos")
        self.setMinimumSize(1000, 500)
        self._resultados = []
        self._db_path = db_path
        self._scanning = False
        self._auto_mode = False
        self._som_ativado = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_title = QLabel("Colares Protetivos")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        self.lbl_status = QLabel("0 colares")
        self.lbl_status.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        header_layout.addWidget(self.lbl_status)

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
        header_layout.addWidget(self.btn_bell)

        layout.addLayout(header_layout)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(10)

        left_widget = QWidget()
        left_widget.setFixedWidth(200)
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(6)

        lbl_filtro = QLabel("Filtrar Ativo:")
        lbl_filtro.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        left_panel.addWidget(lbl_filtro)

        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Digite 3+ letras...")
        self.txt_filtro.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QLineEdit:focus { border-color: #1abc9c; }
        """)
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._on_search_ativos_debounced)
        self.txt_filtro.textChanged.connect(self._debounce_timer.start)
        left_panel.addWidget(self.txt_filtro)

        sep_filtro_pop = QFrame()
        sep_filtro_pop.setFrameShape(QFrame.HLine)
        sep_filtro_pop.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        left_panel.addWidget(sep_filtro_pop)

        lbl_filtro_pop = QLabel("Filtrar por Prob. Mín.:")
        lbl_filtro_pop.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        left_panel.addWidget(lbl_filtro_pop)

        pop_row1 = QHBoxLayout()
        pop_row1.setSpacing(4)
        lbl_up = QLabel("Pop↑:")
        lbl_up.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 8pt;")
        self.spin_pop_upside = QLineEdit("0")
        self.spin_pop_upside.setFixedWidth(50)
        self.spin_pop_upside.setPlaceholderText("%")
        self.spin_pop_upside.setStyleSheet("""
            QLineEdit { background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 3px;
                padding: 2px 4px; font-size: 8pt;
            }
            QLineEdit:focus { border-color: #1abc9c; }
        """)
        self.spin_pop_upside.textChanged.connect(self._on_filtro_pop_changed)
        pop_row1.addWidget(lbl_up)
        pop_row1.addWidget(self.spin_pop_upside)
        pop_row1.addStretch()
        left_panel.addLayout(pop_row1)

        pop_row2 = QHBoxLayout()
        pop_row2.setSpacing(4)
        lbl_dn = QLabel("Pop↓:")
        lbl_dn.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 8pt;")
        self.spin_pop_downside = QLineEdit("0")
        self.spin_pop_downside.setFixedWidth(50)
        self.spin_pop_downside.setPlaceholderText("%")
        self.spin_pop_downside.setStyleSheet("""
            QLineEdit { background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 3px;
                padding: 2px 4px; font-size: 8pt;
            }
            QLineEdit:focus { border-color: #1abc9c; }
        """)
        self.spin_pop_downside.textChanged.connect(self._on_filtro_pop_changed)
        pop_row2.addWidget(lbl_dn)
        pop_row2.addWidget(self.spin_pop_downside)
        pop_row2.addStretch()
        left_panel.addLayout(pop_row2)

        sep_topn = QFrame()
        sep_topn.setFrameShape(QFrame.HLine)
        sep_topn.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        left_panel.addWidget(sep_topn)

        lbl_topn = QLabel("Top N por Ativo:")
        lbl_topn.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        left_panel.addWidget(lbl_topn)

        topn_row = QHBoxLayout()
        topn_row.setSpacing(4)
        self.spin_topn = QSpinBox()
        self.spin_topn.setRange(0, 20)
        self.spin_topn.setValue(0)
        self.spin_topn.setFixedWidth(60)
        self.spin_topn.setToolTip("0 = mostra todos. 1 = só o melhor de cada ativo. 2 = até 2 por ativo, etc.")
        self.spin_topn.setStyleSheet("""
            QSpinBox {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 3px;
                padding: 2px 4px; font-size: 8pt;
            }
            QSpinBox:focus { border-color: #1abc9c; }
        """)
        self.spin_topn.valueChanged.connect(self._on_topn_changed)
        topn_row.addWidget(self.spin_topn)
        topn_row.addStretch()
        left_panel.addLayout(topn_row)

        self.txt_sel_atual = QTextEdit()
        self.txt_sel_atual.setReadOnly(True)
        self.txt_sel_atual.setFixedHeight(50)
        self.txt_sel_atual.setStyleSheet(f"""
            QTextEdit {{
                background-color: #15152a; color: {Palette.GREEN};
                border: 1px solid {Palette.BORDER}; border-radius: 3px;
                font-size: 7pt; padding: 2px;
            }}
        """)
        self.txt_sel_atual.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_panel.addWidget(self.txt_sel_atual)

        self.lista_ativos = QListWidget()
        self.lista_ativos.setStyleSheet("""
            QListWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #2d2d44;
                color: #1abc9c;
            }
        """)
        self.lista_ativos.itemChanged.connect(self._on_asset_check_changed)
        left_panel.addWidget(self.lista_ativos, stretch=1)

        self.btn_todos = QPushButton("(Des)marcar TODOS")
        self.btn_todos.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 4px;
                padding: 4px; font-size: 8pt;
            }
            QPushButton:hover { background-color: #2d2d44; color: #1abc9c; }
        """)
        self.btn_todos.clicked.connect(self._toggle_todos)
        left_panel.addWidget(self.btn_todos)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        left_panel.addWidget(sep)

        self.lbl_selecionados = QLabel("Selecionados: 0 ativos")
        self.lbl_selecionados.setStyleSheet(f"color: {Palette.YELLOW}; font-size: 8pt; font-weight: bold;")
        left_panel.addWidget(self.lbl_selecionados)

        self.btn_scan = QPushButton("🔍 Iniciar Scanner")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #1abc9c; color: #0d0d1a;
                border: none; border-radius: 4px;
                padding: 6px; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #16a085; }
            QPushButton:disabled { background-color: #2d2d44; color: #666; }
            QPushButton[pausado="true"] {
                background-color: #e67e22; color: #fff;
            }
        """)
        self.btn_scan.clicked.connect(self._toggle_scan)
        left_panel.addWidget(self.btn_scan)

        self.btn_regras = QPushButton("📋 Regras")
        self.btn_regras.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8b8be0;
                border: 1px solid #8b8be066; border-radius: 4px;
                padding: 4px; font-size: 8pt;
            }
            QPushButton:hover { background-color: #8b8be022; }
        """)
        self.btn_regras.setVisible(False)
        self.btn_regras.clicked.connect(self._abrir_regras)
        left_panel.addWidget(self.btn_regras)

        self.lbl_scan_status = QLabel("✅ Pronto")
        self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt;")
        left_panel.addWidget(self.lbl_scan_status)

        body_layout.addWidget(left_widget)

        self.table_view = QTableView()
        self.model = ColarTableModel()

        self.proxy = ColarSortProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.proxy.sort(3, Qt.DescendingOrder)

        self.table_view.setModel(self.proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 9))
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setDragEnabled(True)
        header.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header, "colar_table_order")))
        restaurar_ordem_colunas(header, "colar_table_order")
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().hide()
        header.resizeSection(0, 80)
        header.resizeSection(1, 100)
        header.resizeSection(2, 110)
        header.resizeSection(3, 80)
        header.resizeSection(4, 80)
        header.resizeSection(7, 90)
        header.resizeSection(8, 90)
        header.resizeSection(9, 70)
        header.resizeSection(10, 60)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        body_layout.addWidget(self.table_view, stretch=1)

        layout.addLayout(body_layout, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setAutoDefault(False)
        self.btn_fechar.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

        todos_ativos = self._carregar_todos_ativos()
        if todos_ativos:
            self._popular_lista_ativos(todos_ativos)

    def _on_filtro_pop_changed(self):
        up = self.spin_pop_upside.text().strip()
        dn = self.spin_pop_downside.text().strip()
        try:
            up_val = float(up) if up else 0.0
        except ValueError:
            up_val = 0.0
        try:
            dn_val = float(dn) if dn else 0.0
        except ValueError:
            dn_val = 0.0
        self.proxy.set_filtro_pop_upside(up_val)
        self.proxy.set_filtro_pop_downside(dn_val)

    def _on_topn_changed(self, n: int):
        self.proxy.set_top_n(n)
        self._atualizar_status()

    def _on_search_ativos_debounced(self):
        texto = self.txt_filtro.text()
        self.lista_ativos.setUpdatesEnabled(False)
        for i in range(self.lista_ativos.count()):
            item = self.lista_ativos.item(i)
            if i == 0:
                item.setHidden(False)
            else:
                item.setHidden(bool(texto.strip() and texto.upper() not in item.text().upper()))
        self.lista_ativos.setUpdatesEnabled(True)

    def _on_asset_check_changed(self, item):
        self._aplicar_filtro_lista()
        self._restart_scan_if_auto()

    def _toggle_todos(self):
        algum_marcado = any(
            self.lista_ativos.item(i).checkState() == Qt.Checked
            for i in range(1, self.lista_ativos.count())
        )
        estado = Qt.Unchecked if algum_marcado else Qt.Checked
        self.lista_ativos.blockSignals(True)
        for i in range(1, self.lista_ativos.count()):
            self.lista_ativos.item(i).setCheckState(estado)
        self.lista_ativos.blockSignals(False)
        self._aplicar_filtro_lista()
        self._restart_scan_if_auto()

    def _restart_scan_if_auto(self):
        if self._auto_mode:
            self.parar_scan_signal.emit()
            self.iniciar_scan_signal.emit()

    def _aplicar_filtro_lista(self):
        selecionados = []
        todos_marcados = True
        tem_algum = False
        for i in range(1, self.lista_ativos.count()):
            item = self.lista_ativos.item(i)
            if item.checkState() == Qt.Checked:
                selecionados.append(item.text())
                tem_algum = True
            else:
                todos_marcados = False
        selecionados_set = set(selecionados)
        if not tem_algum or todos_marcados:
            self.proxy.set_filtro_ativo("")
        else:
            self.proxy.set_filtro_lista(selecionados_set)
        n_sel = len(selecionados)
        total = self.lista_ativos.count() - 1
        self.lbl_selecionados.setText(f"Selecionados: {n_sel}/{total} ativos")
        if selecionados and not todos_marcados:
            texto = ", ".join(selecionados)
        else:
            texto = "Todos os ativos"
        self.txt_sel_atual.setPlainText(texto)
        self.btn_scan.setEnabled(n_sel > 0 and not self._scanning)
        self.selecao_alterada.emit(selecionados if not todos_marcados else [])
        self._atualizar_status()

    def _atualizar_status(self):
        total = self.proxy.rowCount()
        filtro = self.txt_filtro.text().strip()
        rtd_str = "RTD: ON" if getattr(self, "_rtd_ok", False) else "RTD: ---"
        has_results = getattr(self, "_dados_carregados", False)
        topn_n = self.spin_topn.value()
        topn_suf = f" | Top {topn_n}" if topn_n > 0 else ""
        if total == 0 and filtro:
            self.lbl_status.setText(f"Nenhum colar para '{filtro}' | {rtd_str}")
        elif total == 0:
            if has_results:
                self.lbl_status.setText(f"Nenhum colar viável para a seleção | {rtd_str}")
            else:
                self.lbl_status.setText(f"Aguardando dados... | {rtd_str}")
        elif filtro:
            self.lbl_status.setText(f"{total} colares para '{filtro}'{topn_suf} | {rtd_str}")
        else:
            self.lbl_status.setText(f"{total} colares viáveis{topn_suf} | {rtd_str}")

    def sync_auto_active(self):
        self._auto_mode = True
        self._scanning = False
        self.btn_scan.setText("⏹ Parar Scanner")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: #fff;
                border: none; border-radius: 4px;
                padding: 6px; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        self.btn_scan.setEnabled(True)
        self.lbl_scan_status.setText("🔄 Scanner ligado (a cada ~60s)")
        self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt; font-weight: bold;")

    def restaurar_selecao(self, ativos: list[str]):
        for i in range(1, self.lista_ativos.count()):
            item = self.lista_ativos.item(i)
            item.setCheckState(Qt.Checked if item.text() in ativos else Qt.Unchecked)
        self._aplicar_filtro_lista()

    def _toggle_scan(self):
        if self._auto_mode:
            self._auto_mode = False
            self._scanning = False
            self.btn_scan.setText("🔍 Iniciar Scanner")
            self.btn_scan.setStyleSheet("""
                QPushButton {
                    background-color: #1abc9c; color: #0d0d1a;
                    border: none; border-radius: 4px;
                    padding: 6px; font-size: 9pt; font-weight: bold;
                }
                QPushButton:hover { background-color: #16a085; }
                QPushButton:disabled { background-color: #2d2d44; color: #666; }
            """)
            self.btn_scan.setEnabled(True)
            self.lbl_scan_status.setText("⏹ Scanner parado")
            self.lbl_scan_status.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 8pt;")
            self._aplicar_filtro_lista()
            self.parar_scan_signal.emit()
            parent = self.parent()
            if parent:
                parent._colar_auto_active = False
        else:
            n_sel = sum(1 for i in range(1, self.lista_ativos.count())
                        if self.lista_ativos.item(i).checkState() == Qt.Checked)
            if n_sel == 0 and self.lista_ativos.count() > 1:
                return
            self._auto_mode = True
            self._scanning = False
            self.btn_scan.setText("⏹ Parar Scanner")
            self.btn_scan.setStyleSheet("""
                QPushButton {
                    background-color: #e67e22; color: #fff;
                    border: none; border-radius: 4px;
                    padding: 6px; font-size: 9pt; font-weight: bold;
                }
                QPushButton:hover { background-color: #d35400; }
                QPushButton:disabled { background-color: #2d2d44; color: #666; }
            """)
            self.lbl_scan_status.setText("🔄 Scanner ligado (a cada ~60s)")
            self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt; font-weight: bold;")
            self.iniciar_scan_signal.emit()
            parent = self.parent()
            if parent:
                parent._colar_auto_active = True

    def set_scan_completed(self, n_resultados: int, auto: bool = False):
        if auto and self._auto_mode:
            self._scanning = False
            self.btn_scan.setEnabled(True)
            if n_resultados > 0:
                self.lbl_scan_status.setText(f"🔄 Scanner ligado | {n_resultados} colares")
            else:
                self.lbl_scan_status.setText("🔄 Scanner ligado (a cada ~60s)")
            self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt; font-weight: bold;")
        else:
            self._scanning = False
            self.btn_scan.setEnabled(True)
            if n_resultados > 0:
                self.lbl_scan_status.setText(f"✅ {n_resultados} colares encontrados")
                self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt; font-weight: bold;")
            else:
                self.lbl_scan_status.setText("✅ Nenhum colar viável")
                self.lbl_scan_status.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 8pt;")

    def set_rtd_status(self, conectado: bool):
        self._rtd_ok = conectado
        self._atualizar_status()

    def _on_row_double_clicked(self, index):
        proxy_idx = self.proxy.mapToSource(index)
        row = proxy_idx.row()
        if row < 0 or row >= len(self._resultados):
            return
        r = self._resultados[row]
        self._mostrar_detalhes(r)

    def _mostrar_detalhes(self, r):
        from src.domain.services.calculadora_colar import ResultadoColar

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Montagem Colar — {r.ativo}")
        dialog.setMinimumSize(480, 380)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"<b>{r.ativo}</b> — Colar {r.tipo.value}")
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

        lbl = QLabel("Dias até venc.:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.dias} dias")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep2)

        lbl = QLabel("1. Comprar Ativo:")
        lbl.setStyleSheet(label_style)
        preco_compra_real = r.custo_liquido - r.premio_put + r.premio_call
        val = QLabel(f"{r.ativo} à vista — R$ {preco_compra_real:.2f}")
        val.setToolTip(
            f"Preço de compra efetivo (oferta de venda / ask). "
            f"Spot (último negócio): R$ {r.preco_ativo:.2f}"
        )
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("2. Comprar PUT:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.cod_put} (K={r.strike_put:.2f}) — R$ {r.premio_put:.2f}")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("3. Vender CALL:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.cod_call} (K={r.strike_call:.2f}) — R$ {r.premio_call:.2f}")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep3)

        lbl = QLabel("Custo Líquido:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {r.custo_liquido:.2f}")
        val.setToolTip("Custo total = preço de compra da ação + prêmio da PUT − prêmio recebido da CALL." + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {Palette.YELLOW}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        pnl_b3 = r.pior_retorno - r.custo_b3
        pnl_final = pnl_b3 - r.custo_ir

        lbl = QLabel("Pior Retorno (bruto):")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {r.pior_retorno:.2f}")
        val.setToolTip(
            "Resultado no pior cenário (ativo abaixo do strike PUT no vencimento), antes de custos."
        )
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        lbl = QLabel("− Custos B3:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"−R$ {r.custo_b3:.4f}")
        val.setToolTip("Emolumento + liquidação (2 pernas)." + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {Palette.ORANGE}; font-size: 10pt; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("= Pior pós-B3:")
        lbl.setStyleSheet(label_style)
        b3_color = Palette.GREEN if pnl_b3 > 0 else Palette.RED
        val = QLabel(f"R$ {pnl_b3:.2f}")
        val.setToolTip("Pior resultado após deduzir custos B3." + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {b3_color}; font-size: 10pt; font-family: Consolas;")
        form.addRow(lbl, val)

        if r.custo_ir > 0:
            lbl = QLabel("− IR (15%):")
            lbl.setStyleSheet(label_style)
            val = QLabel(f"−R$ {r.custo_ir:.4f}")
            val.setToolTip("Imposto de Renda (15%) sobre o lucro líquido." + CUSTOS_DISCLOSURE)
            val.setStyleSheet(f"color: {Palette.ORANGE}; font-size: 10pt; font-family: Consolas;")
            form.addRow(lbl, val)

        lbl = QLabel("= Pior Líquido:")
        lbl.setStyleSheet(label_style)
        liq_color = Palette.GREEN if pnl_final > 0 else Palette.RED
        val = QLabel(f"R$ {pnl_final:.2f}")
        val.setToolTip("Pior resultado líquido final (B3 + IR deduzidos)." + CUSTOS_DISCLOSURE)
        val.setStyleSheet(f"color: {liq_color}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("Retorno vs CDI:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{r.pct_ganho*100:.2f}% / {r.pct_cdi:.2f}x CDI ({r.pct_cdi_liquido:.2f}x CDI líquido)")
        val.setToolTip(
            "Percentual de retorno e múltiplos do CDI (bruto e líquido de IR)." + CUSTOS_DISCLOSURE
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

        lbl = QLabel("Risco de Leilão:")
        lbl.setStyleSheet(label_style)
        risco_color = Palette.GREEN if r.risco_leilao.value == "Baixo" else (Palette.ORANGE if r.risco_leilao.value == "Médio" else Palette.RED)
        val = QLabel(r.risco_leilao.value)
        val.setStyleSheet(f"color: {risco_color}; font-size: 10pt; font-weight: bold;")
        form.addRow(lbl, val)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_payoff = QPushButton("📊 Payoff")
        btn_payoff.setAutoDefault(False)
        btn_payoff.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_payoff.clicked.connect(lambda: self._plot_payoff(r))
        btn_row.addWidget(btn_payoff)

        btn_variacao = QPushButton("📈 Ver Variação")
        btn_variacao.setAutoDefault(False)
        btn_variacao.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_variacao.clicked.connect(lambda: self._mostrar_variacao(r))
        btn_row.addWidget(btn_variacao)

        btn_grafico = QPushButton("📊 Ver Gráfico")
        btn_grafico.setAutoDefault(False)
        btn_grafico.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        n_sig = max(5, int(r.dias * 5 / 7))
        btn_grafico.clicked.connect(lambda: self._plot_historico(r.ativo, r.preco_ativo, n_sig))
        btn_row.addWidget(btn_grafico)

        btn_explicar = QPushButton("🔍 Explicar")
        btn_explicar.setAutoDefault(False)
        btn_explicar.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_explicar.clicked.connect(lambda: self._explicar_estrategia(r))
        btn_row.addWidget(btn_explicar)

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
        btn_pnt.clicked.connect(lambda: self._abrir_boleta_colar(r))
        btn_row.addWidget(btn_pnt)

        btn_export = QPushButton("📋 Exportar Debug")
        btn_export.setAutoDefault(False)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_export.clicked.connect(lambda: self._exportar_debug(r))
        btn_row.addWidget(btn_export)

        btn_row.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)

        layout.addLayout(btn_row)

        dialog.exec_()

    def _abrir_boleta_colar(self, r):
        from src.ui.desktop.boleta_dialog import BoletaDialog
        dlg = BoletaDialog("COLAR", r, self._db_path, self)
        dlg.exec_()

    def _explicar_estrategia(self, r):
        from src.domain.services.calculadora_colar import ResultadoColar

        S0 = r.preco_ativo
        Kc, Kp = r.strike_call, r.strike_put
        Pc, Pp = r.premio_call, r.premio_put
        custo = r.custo_liquido
        pior = r.pior_retorno
        melhor = Kc - custo

        html = "\n".join([
            "<h3>📖 Explicação — Colar Protetivo (Coberto)</h3>",
            f"<p><b>{r.ativo}</b> &mdash; {r.tipo.value}</p>",
            "<hr>",
            "<p><b>O que é esta estratégia?</b><br>",
            "Você compra a ação, compra uma PUT de proteção e vende uma CALL para financiar a PUT. ",
            "O lucro máximo é limitado pelo strike da CALL, e a perda máxima é limitada pelo strike da PUT.</p>",
            "<hr>",
            "<p><b>Montagem:</b></p>",
            "<ul>",
            f"<li>Comprar ação: <b>−R$ {custo - Pp + Pc:.2f}</b></li>",
            f"<li>Comprar PUT {r.cod_put} K={Kp:.2f}: <b>−R$ {Pp:.2f}</b></li>",
            f"<li>Vender CALL {r.cod_call} K={Kc:.2f}: <b>+R$ {Pc:.2f}</b></li>",
            f"<li><b>Custo líquido = R$ {custo:.2f}</b> ({custo - Pp + Pc:.2f} + {Pp:.2f} − {Pc:.2f})</li>",
            "</ul>",
            "<hr>",
            "<p><b>Cenários no vencimento:</b></p>",
            "<ul>",
            f"<li><b>Se ativo &lt; R$ {Kp:.2f}:</b> PUT ITM → exerce, vende ação a R$ {Kp:.2f}. "
            f"{'Pior retorno' if pior >= 0 else 'Perda máxima'} de <b>R$ {pior:.2f}</b> ({r.pct_ganho*100:.2f}% / {r.pct_cdi:.2f}x CDI)</li>",
            f"<li><b>Se ativo entre R$ {Kp:.2f} e R$ {Kc:.2f}:</b> ambas OTM → lucro varia linearmente.</li>",
            f"<li><b>Se ativo &gt; R$ {Kc:.2f}:</b> CALL ITM → ação vendida a R$ {Kc:.2f}. "
            f"Lucro máximo de <b>R$ {melhor:.2f}</b>.</li>",
            "</ul>",
            "<hr>",
            "<p><b>Risco de Leilão:</b> "
            f"{r.risco_leilao.value} — "
            f"{'Baixo risco de leilão' if r.risco_leilao.value == 'Baixo' else 'Pode haver dificuldade na execução'}</p>",
            "<hr>",
            f"<p><b>Probabilidades (IV médio {((r.iv_call + r.iv_put)/2):.1f}%):</b><br>"
            f"📈 Alta > R$ {Kc:.2f}: <b>{f'{r.pop_upside:.1f}%' if r.pop_upside is not None else '-'}</b> "
            f"(call exercida, lucro máximo)<br>"
            f"📉 Baixa < R$ {Kp:.2f}: <b>{f'{r.pop_downside:.1f}%' if r.pop_downside is not None else '-'}</b> "
            f"(put exercida, pior caso)<br>"
            f"📊 Meio (R$ {Kp:.2f}–{Kc:.2f}): <b>{f'{max(0, 100 - r.pop_upside - r.pop_downside):.1f}%' if r.pop_upside is not None and r.pop_downside is not None else '-'}</b></p>",
            "<hr>",
            f"<p><b>Resumo:</b><br>"
            f"O pior retorno de R$ {pior:.2f} ocorre se o ativo fechar abaixo de R$ {Kp:.2f}. "
            f"O melhor retorno de R$ {melhor:.2f} ocorre se o ativo fechar acima de R$ {Kc:.2f}. "
            f"A relação CDI de {r.pct_cdi:.2f}x é calculada sobre o pior caso.",
            "</p>",
        ])
        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Explicação — Colar {r.ativo}")
        dialog.setMinimumSize(650, 450)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        texto = QTextEdit()
        texto.setReadOnly(True)
        texto.setHtml(html)
        texto.setStyleSheet(f"""
            QTextEdit {{
                background-color: #15152a; color: #e0e0e0;
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                font-size: 10pt; padding: 12px;
            }}
        """)
        layout.addWidget(texto, stretch=1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _exportar_debug(self, r):
        from PySide6.QtWidgets import QApplication, QMessageBox

        lines = [
            "=== DEBUG COLAR PROTETIVO ===",
            "",
            "--- INPUTS ---",
            f"Ativo:          {r.ativo}",
            f"Spot:           R$ {r.preco_ativo:.4f}",
            f"Cod Call:       {r.cod_call}",
            f"Strike Call:    R$ {r.strike_call:.4f}",
            f"Cod Put:        {r.cod_put}",
            f"Strike Put:     R$ {r.strike_put:.4f}",
            f"Premio Call:    R$ {r.premio_call:.4f}  (OCP)",
            f"Premio Put:     R$ {r.premio_put:.4f}  (OVD)",
            f"DTE:            {r.dias}d",
            f"IV Call:        {r.iv_call:.2f}%",
            f"IV Put:         {r.iv_put:.2f}%",
            f"Vencimento:     {r.vencimento}",
            "",
            "--- MONTAGEM ---",
            f"Custo liquido:      R$ {r.custo_liquido:.4f}",
            f"Pior retorno:       R$ {r.pior_retorno:.4f}",
            f"Pct ganho:          {r.pct_ganho*100:.4f}%",
            f"Pct CDI:            {r.pct_cdi:.2f}x",
            "",
            "--- PROBABILIDADES ---",
            f"Pop Upside (>{r.strike_call:.2f}): {f'{r.pop_upside:.1f}%' if r.pop_upside is not None else 'N/D'}",
            f"Pop Downside (<{r.strike_put:.2f}): {f'{r.pop_downside:.1f}%' if r.pop_downside is not None else 'N/D'}",
            "",
            "--- RISCO ---",
            f"Risco Leilao:       {r.risco_leilao.value}",
            f"Em leilao:          {r.em_leilao}",
            f"Tipo:               {r.tipo.value}",
            f"Viavel:             {r.viavel}",
        ]
        texto = "\n".join(lines)
        QApplication.clipboard().setText(texto)
        QMessageBox.information(self, "Debug Exportado",
                                "Dados de debug copiados para a área de transferência.\n"
                                "Cole (Ctrl+V) aqui no chat.")

    def _plot_payoff(self, r):
        import numpy as np
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        preco_compra = r.custo_liquido - r.premio_put + r.premio_call
        S = r.preco_ativo
        Kp = r.strike_put
        Kc = r.strike_call
        Pp = r.premio_put
        Pc = r.premio_call
        custo = r.custo_liquido

        x_min = min(Kp, S) * 0.85
        x_max = max(Kc, S) * 1.15
        x = np.linspace(x_min, x_max, 500)

        stock_pnl = x - preco_compra
        put_pnl = np.maximum(Kp - x, 0) - Pp
        call_pnl = Pc - np.maximum(x - Kc, 0)
        total_pnl = stock_pnl + put_pnl + call_pnl

        pior_ret = Kp - custo
        melhor_ret = Kc - custo
        cdi_periodo = r.pct_ganho / r.pct_cdi if r.pct_cdi > 0 else 0
        pct_melhor = (melhor_ret / custo) * 100
        pct_melhor_cdi = pct_melhor / (cdi_periodo * 100) if cdi_periodo > 0 else 0
        pct_pior = (pior_ret / custo) * 100

        BG = '#0d0d0d'; TEXT = '#c0c0c0'; WHITE = '#ffffff'; RED = '#ff3355'
        ACCENT = '#ffc107'; FILL_BLUE = '#1a5276'; BLUE = '#2196f3'; GREEN = '#4caf50'

        fig = Figure(figsize=(9, 5), facecolor=BG)
        ax = fig.add_subplot(111, facecolor=BG)

        ax.plot(x, total_pnl, color=ACCENT, linewidth=2.0, label='Payoff')

        y_range = total_pnl.max() - total_pnl.min()
        y_pad = max(y_range * 0.08, max(abs(total_pnl.max()), abs(total_pnl.min())) * 0.3, 0.3)
        hover_vline = ax.axvline(0, color=ACCENT, linewidth=0.8, linestyle=':', alpha=0.5, visible=False, zorder=5)
        hover_hline = ax.axhline(0, color=ACCENT, linewidth=0.8, linestyle=':', alpha=0.5, visible=False, zorder=5)
        hover_text = ax.text(
            0.02, 0.98, '', fontsize=8, color='#fff', visible=False, zorder=10,
            transform=ax.transAxes, ha='left', va='top',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=ACCENT, alpha=0.9),
        )
        def _on_hover(event):
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(total_pnl.min() - y_pad, total_pnl.max() + y_pad)
            if event.inaxes != ax or event.xdata is None:
                hover_text.set_visible(False)
                hover_vline.set_visible(False)
                hover_hline.set_visible(False)
                fig.canvas.draw_idle()
                return
            idx = np.argmin(np.abs(x - event.xdata))
            xv, yv = x[idx], total_pnl[idx]
            hover_text.set_text(f'Preço: R$ {xv:.2f}  |  PnL: R$ {yv:+.2f}')
            hover_text.set_visible(True)
            hover_vline.set_xdata([xv, xv])
            hover_vline.set_visible(True)
            hover_hline.set_ydata([yv, yv])
            hover_hline.set_visible(True)
            fig.canvas.draw_idle()

        ax.axhline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.3)
        ax.axvline(S, color=WHITE, linewidth=0.7, linestyle='--', alpha=0.8, label=f'Spot {S:.2f}')
        ax.axvline(Kp, color=RED, linewidth=0.7, linestyle='--', alpha=0.8, label=f'K Put {Kp:.2f}')
        ax.axvline(Kc, color=ACCENT, linewidth=0.7, linestyle='--', alpha=0.8, label=f'K Call {Kc:.2f}')
        ax.axhline(pior_ret, color=RED, linewidth=0.6, linestyle='--', alpha=0.4, label=f'Pior R$ {pior_ret:.2f}')

        ax.fill_between(x, 0, total_pnl, where=(total_pnl >= 0), color=FILL_BLUE, alpha=0.12)
        ax.fill_between(x, 0, total_pnl, where=(total_pnl < 0), color=RED, alpha=0.1)

        cor_melhor = BLUE if r.viavel else RED
        cor_pior = BLUE if r.viavel else RED

        x_centro_lucro = (x_max + Kc) / 2
        ax.annotate(
            f'Melhor: {pct_melhor:.2f}% / {pct_melhor_cdi:.2f}x CDI',
            xy=(Kc, melhor_ret), fontsize=7.5, color=cor_melhor,
            ha='center', va='bottom',
            xytext=(x_centro_lucro, melhor_ret + abs(melhor_ret) * 0.25),
            arrowprops=dict(arrowstyle='->', color=cor_melhor, lw=0.7),
        )

        x_centro_perda = (x_min + Kp) / 2
        ax.annotate(
            f'Pior: {pct_pior:.2f}% / {r.pct_cdi:.2f}x CDI',
            xy=(Kp, pior_ret), fontsize=7.5, color=cor_pior,
            ha='center', va='top',
            xytext=(x_centro_perda, pior_ret - abs(pior_ret) * 0.25),
            arrowprops=dict(arrowstyle='->', color=cor_pior, lw=0.7),
        )

        ax.set_xlabel('Preço do Ativo no Vencimento (R$)', color=TEXT, fontsize=9)
        ax.set_ylabel('Lucro / Prejuízo (R$)', color=TEXT, fontsize=9)
        ax.set_title(f'Payoff Colar — {r.ativo}', color='#e0e0e0', fontsize=11, fontweight='bold')

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(total_pnl.min() - y_pad, total_pnl.max() + y_pad)

        ax.tick_params(colors=TEXT, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#333')
        ax.legend(loc='best', fontsize=7, labelcolor=TEXT, facecolor='#1a1a1a', edgecolor='#333')

        fig.tight_layout(pad=1.5)

        payoff_dialog = QDialog(self, Qt.Window)
        payoff_dialog.setWindowTitle(f"Payoff — {r.ativo}")
        payoff_dialog.setMinimumSize(850, 520)
        payoff_layout = QVBoxLayout(payoff_dialog)
        payoff_layout.setContentsMargins(8, 8, 8, 8)
        canvas = FigureCanvas(fig)
        fig.canvas.mpl_connect('motion_notify_event', _on_hover)
        payoff_layout.addWidget(canvas)

        footer = QLabel(
            f"<b>Comprar Ativo:</b> {r.ativo} à vista — R$ {preco_compra:.2f} (ask)<br>"
            f"<b>Vender Call:</b> {r.cod_call} K={Kc:.2f} — +R$ {Pc:.2f} (prêmio recebido)<br>"
            f"<b>Comprar Put:</b> {r.cod_put} K={Kp:.2f} — −R$ {Pp:.2f} (prêmio pago)<br>"
            f"<b>Custo:</b> R$ {custo:.2f}  |  "
            f"<b>Pior:</b> {pct_pior:.2f}% / {r.pct_cdi:.2f}x CDI"
        )
        footer.setStyleSheet(f"""
            QLabel {{
                color: {Palette.TEXT_SECONDARY};
                font-size: 8pt;
                font-family: Consolas;
                padding: 4px 0;
            }}
        """)
        footer.setTextFormat(Qt.RichText)
        payoff_layout.addWidget(footer)

        btn_close = QPushButton("Fechar")
        btn_close.setAutoDefault(False)
        btn_close.clicked.connect(payoff_dialog.close)
        payoff_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        payoff_dialog.exec_()

    def _plot_historico(self, ativo: str, preco_atual: float = None, n_sessoes: int = 21):
        from PySide6.QtWidgets import QMessageBox
        import numpy as np
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import matplotlib.dates as mdates

        client = OpcoesNetClient()
        candles = client.get_stock_history_formatted(ativo)
        if not candles:
            QMessageBox.information(self, "Gráfico", f"Não foi possível obter histórico de {ativo}.")
            return

        import datetime
        dates = []
        opens, highs, lows, closes = [], [], [], []
        volumes = []
        vol_hists, vol_impls = [], []
        for c in candles:
            d = c.get("date")
            if isinstance(d, str):
                dt = datetime.datetime.strptime(d[:10], "%Y-%m-%d")
            else:
                continue
            dates.append(dt)
            opens.append(c.get("open"))
            highs.append(c.get("high"))
            lows.append(c.get("low"))
            closes.append(c.get("close"))
            volumes.append(c.get("volume"))
            vol_hists.append(c.get("vol_hist"))
            vol_impls.append(c.get("vol_impl"))

        has_vol = any(v is not None for v in vol_hists) or any(v is not None for v in vol_impls)

        BG = '#0d0d0d'; TEXT = '#c0c0c0'; WHITE = '#ffffff'
        GREEN = '#4caf50'; RED = '#ff3355'; BLUE = '#2196f3'
        ACCENT = '#ffc107'

        n_sub = 2 if has_vol else 1
        fig = Figure(figsize=(11, 6.5), facecolor=BG)
        heights = [3, 1] if n_sub == 2 else [3]
        gs = fig.add_gridspec(n_sub, 1, height_ratios=heights, hspace=0.08)

        # --- Top subplot: Candles + Gauss sobreposta ---
        ax1 = fig.add_subplot(gs[0], facecolor=BG)
        width = 0.6
        for i in range(len(dates)):
            color = GREEN if closes[i] >= opens[i] else RED
            ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=0.8, alpha=0.7)
            ax1.bar(dates[i], closes[i] - opens[i], width, bottom=opens[i], color=color, alpha=0.85)

        ax1.set_title(f"{ativo} — Histórico de Preços", color='#e0e0e0', fontsize=11, fontweight='bold')
        ax1.tick_params(colors=TEXT, labelsize=8)
        ax1.set_ylabel('Preço (R$)', color=TEXT, fontsize=9)
        for s in ax1.spines.values():
            s.set_color('#333')
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
        ax1.tick_params(axis='x', colors=TEXT)
        ax1.set_xlim(dates[0], dates[-1])

        if preco_atual is not None and preco_atual > 0:
            ax1.axhline(preco_atual, color=WHITE, linewidth=1.0, linestyle='--', alpha=0.6, zorder=4)
            ax1.text(dates[-1], preco_atual, f'Spot R${preco_atual:.2f}',
                     ha='right', va='bottom', color=WHITE, fontsize=7, alpha=0.8,
                     bbox=dict(boxstyle='round,pad=0.15', facecolor='#1a1a1a', edgecolor='none', alpha=0.6))

        # ── Hover tooltip ──
        hover_annot = ax1.annotate(
            '', xy=(0, 0), fontsize=7.5, color='#fff',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=ACCENT, alpha=0.9),
            ha='center', va='center', visible=False, zorder=10,
        )
        hover_vline = ax1.axvline(0, color=ACCENT, linewidth=0.6, linestyle=':', alpha=0.3, visible=False, zorder=5)

        def _on_hover(event):
            if hasattr(ax1, 'get_xlim') and hasattr(ax1, 'get_ylim'):
                ax1.set_xlim(ax1.get_xlim())
                ax1.set_ylim(ax1.get_ylim())
            if event.inaxes != ax1 or event.xdata is None:
                hover_annot.set_visible(False)
                hover_vline.set_visible(False)
                fig.canvas.draw_idle()
                return
            import matplotlib.dates as mdates
            t = mdates.num2date(event.xdata).replace(tzinfo=None)
            idx = min(range(len(dates)), key=lambda i: abs((dates[i] - t).total_seconds()))
            d = dates[idx]
            hover_annot.xy = (mdates.date2num(d), highs[idx])
            hover_annot.set_text(
                f"{d.strftime('%d/%m/%Y')}  "
                f"O={opens[idx]:.2f} H={highs[idx]:.2f} L={lows[idx]:.2f} C={closes[idx]:.2f}"
                + (f"  Vol={volumes[idx]:,.0f}" if idx < len(volumes) and volumes[idx] is not None else "")
            )
            hover_annot.set_visible(True)
            hover_vline.set_xdata([mdates.date2num(d), mdates.date2num(d)])
            hover_vline.set_visible(True)
            fig.canvas.draw_idle()

        fig.canvas.mpl_connect('motion_notify_event', _on_hover)

        # Sigma levels + Gauss inset
        if len(closes) > 10:
            from scipy.stats import norm
            prices_arr = np.array(closes)
            log_ret = np.diff(np.log(prices_arr))
            sigma_daily = np.std(log_ret)
            sigma_periodo = sigma_daily * np.sqrt(n_sessoes)
            spot = closes[-1]
            sigmas = [spot * (1 + i * sigma_periodo) for i in range(-3, 4) if i != 0]
            ylo = min(min(sigmas), prices_arr.min())
            yhi = max(max(sigmas), prices_arr.max())
            pad = (yhi - ylo) * 0.03
            ax1.set_ylim(ylo - pad, yhi + pad)
            for i in range(-3, 4):
                if i == 0: continue
                p = spot * (1 + i * sigma_periodo)
                ax1.axhline(p, color=ACCENT, linewidth=0.5, linestyle=':', alpha=0.25)
                ax1.text(dates[-1], p, f'{i}σ R${p:.2f}',
                         ha='right', va='center', color=ACCENT, fontsize=6.5, alpha=0.7,
                         bbox=dict(boxstyle='round,pad=0.15', facecolor='#1a1a1a', edgecolor='none', alpha=0.6))
            # Gauss inset (corner)
            x_gauss = np.linspace(-3.5*sigma_periodo, 3.5*sigma_periodo, 300)
            y_gauss = norm.pdf(x_gauss, 0, sigma_periodo)
            ax_inset = ax1.inset_axes([0.02, 0.65, 0.18, 0.28], facecolor='#1a1a1a')
            ax_inset.plot(x_gauss, y_gauss, color=ACCENT, linewidth=1.2, alpha=0.8)
            ax_inset.fill_between(x_gauss, 0, y_gauss, color=ACCENT, alpha=0.1)
            ax_inset.axvline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.3)
            for i in range(1, 4):
                for s in (-i*sigma_periodo, i*sigma_periodo):
                    ax_inset.axvline(s, color=ACCENT, linewidth=0.4, linestyle=':', alpha=0.2)
            ax_inset.set_facecolor('#1a1a1a')
            ax_inset.tick_params(colors=TEXT, labelsize=5)
            for spine in ax_inset.spines.values():
                spine.set_color('#333')
            ax_inset.set_title(f'{n_sessoes} preg', color=TEXT, fontsize=6)
            ax_inset.set_ylabel('dens.', color=TEXT, fontsize=5)

        # --- Bottom subplot: Volume + Volatilidade ---
        if has_vol:
            ax2 = fig.add_subplot(gs[1], facecolor=BG)
            has_vol_data = any(v is not None for v in volumes)
            if has_vol_data:
                vol_max = max(v for v in volumes if v is not None) if any(v is not None for v in volumes) else 1
                vol_norm = [v / vol_max if v is not None else 0 for v in volumes]
                colors_vol = [GREEN if closes[i] >= opens[i] else RED for i in range(len(dates))]
                ax2.bar(dates, vol_norm, width=width, color=colors_vol, alpha=0.7)

            ax2_twin = ax2.twinx()
            has_hist = any(v is not None for v in vol_hists)
            has_impl = any(v is not None for v in vol_impls)
            if has_hist:
                hist_data = [(dates[i], vol_hists[i]) for i in range(len(vol_hists)) if vol_hists[i] is not None]
                if hist_data:
                    h_dates, h_vals = zip(*hist_data)
                    ax2_twin.plot(h_dates, h_vals, color=BLUE, linewidth=1.0, alpha=0.8, label='Vol. Hist.')
            if has_impl:
                impl_data = [(dates[i], vol_impls[i]) for i in range(len(vol_impls)) if vol_impls[i] is not None]
                if impl_data:
                    i_dates, i_vals = zip(*impl_data)
                    ax2_twin.plot(i_dates, i_vals, color=RED, linewidth=1.0, alpha=0.8, label='Vol. Impl.')
            ax2_twin.set_ylabel('Volatilidade', color=TEXT, fontsize=9)
            ax2_twin.tick_params(colors=TEXT, labelsize=7)
            ax2_twin.legend(loc='upper left', fontsize=7, labelcolor=TEXT, facecolor='#1a1a1a', edgecolor='#333')

            ax2.set_ylabel('Volume (norm.)', color=TEXT, fontsize=9)
            ax2.tick_params(colors=TEXT, labelsize=7)
            for s in ax2.spines.values():
                s.set_color('#333')
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

        fig.tight_layout(pad=1.5)

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Gráfico — {ativo}")
        dialog.setMinimumSize(950, 580)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas, stretch=1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _mostrar_variacao(self, r, n_sessoes=None):
        from PySide6.QtWidgets import QMessageBox
        from datetime import date, timedelta
        import re
        import numpy as np
        from scipy.stats import norm
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        if n_sessoes is None:
            n_sessoes = max(5, int(r.dias * 5 / 7))

        client = OpcoesNetClient()
        hoje = date.today()
        raw = client.get_variacao(
            r.ativo,
            data_inicial=(hoje - timedelta(days=365)).strftime("%d/%m/%Y"),
            data_final=hoje.strftime("%d/%m/%Y"),
        )
        if not raw:
            QMessageBox.information(self, "Variação", "Não foi possível obter dados.")
            return

        dados = raw.get("data", {})
        chave_alvo = None
        for k in dados:
            if str(n_sessoes) in k:
                chave_alvo = k
                break
        if not chave_alvo:
            max_n = 0
            for k in dados:
                nums = re.findall(r'\d+', k)
                if nums:
                    n = int(nums[-1])
                    if n > max_n:
                        max_n = n
                        chave_alvo = k
            if not chave_alvo:
                chave_alvo = list(dados.keys())[0]
        bins = dados[chave_alvo]
        total_obs = sum(b["quantidade"] for b in bins)
        dias_neg = raw.get("diasComNegociacao", 0)

        CLASS_KEY = "classifica\u00e7\u00e3o"
        cents, wts = [], []
        for b in bins:
            q = b["quantidade"]
            if q <= 0:
                continue
            rot = b[CLASS_KEY]
            nums = [float(x.replace(",", ".")) for x in re.findall(r'[\d,.]+', rot)]
            if "Menos" in rot:
                c = nums[0] / 2
            elif "Mais" in rot:
                c = nums[0] * 1.5
            elif len(nums) >= 2:
                c = (nums[0] + nums[1]) / 2
            else:
                c = nums[0]
            cents.append(c)
            wts.append(q)

        media = sum(c * w for c, w in zip(cents, wts)) / sum(wts) if wts else 0
        desvio = (sum(w * (c - media) ** 2 for c, w in zip(cents, wts)) / sum(wts)) ** 0.5 if wts else 0

        pct_call = ((r.strike_call - r.preco_ativo) / r.preco_ativo) * 100
        pct_put = ((r.strike_put - r.preco_ativo) / r.preco_ativo) * 100
        spot = r.preco_ativo

        def preco_no_sigma(n_sigma):
            return spot * (1 + n_sigma * desvio / 100)

        BG = '#0d0d0d'; TEXT = '#c0c0c0'; ACCENT = '#ffc107'
        BLUE = '#2196f3'; GREEN = '#4caf50'; RED = '#ff3355'; PURPLE = '#9c27b0'

        fig = Figure(figsize=(11, 5.5), facecolor=BG)
        ax1 = fig.add_subplot(121, facecolor=BG)
        rotulos = [b[CLASS_KEY] for b in bins]
        vals = [b["percentual"] for b in bins]
        cores_b = [BLUE, GREEN, ACCENT, RED][:len(vals)]
        ax1.bar(range(len(vals)), vals, color=cores_b, alpha=0.7, width=0.6, edgecolor='#333', linewidth=0.5)
        for i, v in enumerate(vals):
            ax1.text(i, v + 0.5, f"{v:.1f}%", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
        ax1.set_xticks(range(len(vals)))
        ax1.set_xticklabels(rotulos, color=TEXT, fontsize=7)
        ax1.set_ylabel("% das observacoes", color=TEXT, fontsize=9)
        ax1.set_title(f"{r.ativo} - Variacao em ~{n_sessoes} pregoes\n{dias_neg} dias de amostra", color='#e0e0e0', fontsize=10, fontweight='bold')
        ax1.set_facecolor(BG)
        ax1.tick_params(colors=TEXT, labelsize=8)
        ax1.set_ylim(0, max(vals) * 1.25)
        for s in ax1.spines.values():
            s.set_color('#333')
        ax1.text(0.98, 0.98, f"Spot: R${spot:.2f}\nK Call: R${r.strike_call:.2f}\nK Put: R${r.strike_put:.2f}",
                 transform=ax1.transAxes, fontsize=7, verticalalignment='top', horizontalalignment='right',
                 color=TEXT, bbox=dict(boxstyle='round', facecolor='#1a1a1a', edgecolor='#333'))

        ax2 = fig.add_subplot(122, facecolor=BG)
        x_lim = max(desvio * 4, 12)
        x = np.linspace(-x_lim, x_lim, 800)
        y = norm.pdf(x, 0, desvio) if desvio > 0 else np.zeros_like(x)
        y_max = max(y) * 1.45
        ax2.plot(x, y, color=ACCENT, linewidth=2.5, label='Dist. Normal')
        ax2.set_facecolor(BG)
        ax2.set_xlim(-x_lim, x_lim)
        ax2.set_ylim(-y_max * 0.3, y_max)
        ax2.fill_between(x, 0, y, where=(x >= -desvio) & (x <= desvio), color=BLUE, alpha=0.12)
        ax2.fill_between(x, 0, y, where=(x >= desvio) & (x <= 2 * desvio), color=GREEN, alpha=0.07)
        ax2.fill_between(x, 0, y, where=(x >= -2 * desvio) & (x <= -desvio), color=GREEN, alpha=0.07)
        ax2.fill_between(x, 0, y, where=(x >= 2 * desvio) & (x <= 3 * desvio), color=RED, alpha=0.04)
        ax2.fill_between(x, 0, y, where=(x >= -3 * desvio) & (x <= -2 * desvio), color=RED, alpha=0.04)

        ax2.text(0, y_max * 0.88, "68%", ha='center', va='center', color=BLUE, fontsize=12, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=BLUE, alpha=0.9))
        ax2.text(1.5 * desvio, y_max * 0.62, "13.5%", ha='center', color=GREEN, fontsize=8)
        ax2.text(-1.5 * desvio, y_max * 0.62, "13.5%", ha='center', color=GREEN, fontsize=8)
        ax2.text(2.5 * desvio, y_max * 0.35, "2.35%", ha='center', color=RED, fontsize=7)
        ax2.text(-2.5 * desvio, y_max * 0.35, "2.35%", ha='center', color=RED, fontsize=7)

        ax2.axvline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.2)
        for i in range(1, 4):
            cor = [BLUE, GREEN, RED][i - 1]
            ax2.axvline(i * desvio, color=cor, linewidth=0.6, linestyle='--', alpha=0.3)
            ax2.axvline(-i * desvio, color=cor, linewidth=0.6, linestyle='--', alpha=0.3)

        eixo_y_seta = -y_max * 0.08
        eixo_y_texto = -y_max * 0.15
        for i in range(-3, 4):
            variacao_pct = i * desvio
            cor = ACCENT if i == 0 else ([BLUE, GREEN, RED][abs(i) - 1] if abs(i) <= 3 else TEXT)
            preco_r = preco_no_sigma(i)
            ax2.annotate('', xy=(variacao_pct, 0), xytext=(variacao_pct, eixo_y_seta),
                         arrowprops=dict(arrowstyle='->', color=cor, lw=1.5, alpha=0.8))
            texto_preco = f"R${preco_r:.2f}" + (" (spot)" if i == 0 else "")
            ax2.text(variacao_pct, eixo_y_texto, texto_preco, ha='center', va='top',
                     color=cor, fontsize=7.5, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='#1a1a1a', edgecolor=cor, alpha=0.8))
            ax2.text(variacao_pct, eixo_y_seta - y_max * 0.04, f"{i:+d}s" if i != 0 else "0",
                     ha='center', va='top', color=TEXT, fontsize=6.5, alpha=0.6)

        if abs(pct_call - pct_put) < 0.1:
            pct_k = (pct_call + pct_put) / 2
            z_k = abs(pct_k) / desvio if desvio > 0 else 0
            ax2.axvline(pct_k, color=PURPLE, linewidth=2.5, linestyle='-', alpha=0.95,
                        label=f'K R${r.strike_call:.2f} (Z={z_k:.2f})')
            ax2.axvspan(pct_k - 0.5, pct_k + 0.5, color=PURPLE, alpha=0.08)
            ax2.text(pct_k, y_max * 0.50, f"Strike no percentil {norm.cdf(z_k)*100:.0f}%",
                     ha='center', va='center', color=PURPLE, fontsize=7.5, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=PURPLE, alpha=0.85))
        else:
            ax2.axvline(pct_call, color=ACCENT, linewidth=2, linestyle='-', alpha=0.9, label=f'K Call {r.strike_call:.2f} ({pct_call:+.1f}%)')
            ax2.axvline(pct_put, color=RED, linewidth=2, linestyle='-', alpha=0.9, label=f'K Put {r.strike_put:.2f} ({pct_put:+.1f}%)')

        ax2.axhline(0, color=TEXT, linewidth=0.4, alpha=0.15)
        ax2.set_xlabel('Variacao em relacao ao spot (%)', color=TEXT, fontsize=9)
        ax2.set_ylabel('Densidade', color=TEXT, fontsize=9)
        ax2.set_title("Dist. Normal - Probabilidades e Precos Correspondentes", color='#e0e0e0', fontsize=10, fontweight='bold')
        ax2.tick_params(colors=TEXT, labelsize=8)
        for s in ax2.spines.values():
            s.set_color('#333')
        leg = ax2.legend(loc='upper right', fontsize=7, labelcolor=TEXT, facecolor='#1a1a1a', edgecolor='#333')
        leg.get_frame().set_alpha(0.95)
        ax2.text(0.02, 0.98, f"Media: {media:.1f}%\nDesvio: {desvio:.1f}%\nObs: {total_obs}",
                 transform=ax2.transAxes, fontsize=7, verticalalignment='top', color=TEXT,
                 bbox=dict(boxstyle='round', facecolor='#1a1a1a', edgecolor='#333'))
        fig.tight_layout()

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit

        input_style = """
            QLineEdit {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 4px;
                padding: 4px 8px; font-size: 9pt;
            }
            QLineEdit:focus { border-color: #1abc9c; }
        """

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Variacao - {r.ativo}")
        dialog.setMinimumSize(1050, 580)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel(f"<b>{r.ativo}</b>  |  Spot: R${spot:.2f}  |  K: R${r.strike_call:.2f} / R${r.strike_put:.2f}")
        title.setStyleSheet(f"font-size: 10pt; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        control_row = QHBoxLayout()
        control_row.setSpacing(8)
        lbl_periodo = QLabel("Período (pregões):")
        lbl_periodo.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;")
        inp_periodo = QLineEdit(str(n_sessoes))
        inp_periodo.setFixedWidth(60)
        inp_periodo.setStyleSheet(input_style)
        btn_atualizar = QPushButton("Atualizar")
        btn_atualizar.setAutoDefault(False)
        btn_atualizar.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 4px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        def _reload():
            try:
                novo_n = int(inp_periodo.text().strip())
                if novo_n >= 5:
                    dialog.accept()
                    self._mostrar_variacao(r, novo_n)
            except ValueError:
                pass
        btn_atualizar.clicked.connect(_reload)
        control_row.addWidget(lbl_periodo)
        control_row.addWidget(inp_periodo)
        control_row.addWidget(btn_atualizar)
        control_row.addStretch()
        layout.addLayout(control_row)

        canvas = FigureCanvas(fig)
        layout.addWidget(canvas, stretch=1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _carregar_todos_ativos(self) -> list[str]:
        if not self._db_path:
            return []
        try:
            from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
            repo = InstrumentoRepository(self._db_path)
            inst_map = repo.get_all_mapped()
            ativos = sorted(set(
                inst.ativo for inst in inst_map.values()
                if inst.ativo
            ))
            return ativos
        except Exception:
            return []

    def _popular_lista_ativos(self, ativos: list[str]):
        whitelist = ler_whitelist_colar(self._db_path)
        usar_whitelist = bool(whitelist)
        self.lista_ativos.blockSignals(True)
        self.lista_ativos.clear()

        item_todos = QListWidgetItem("TODOS")
        item_todos.setFlags(item_todos.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        item_todos.setForeground(QColor(Palette.YELLOW))
        item_todos.setToolTip("Mostrar todos os ativos")
        font_todos = QFont()
        font_todos.setBold(True)
        item_todos.setFont(font_todos)
        self.lista_ativos.addItem(item_todos)

        for ativo in ativos:
            item = QListWidgetItem(ativo)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if usar_whitelist:
                item.setCheckState(Qt.Checked if ativo in whitelist else Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)
            item.setForeground(QColor(Palette.TEXT_PRIMARY))
            self.lista_ativos.addItem(item)

        self.lista_ativos.blockSignals(False)
        self._aplicar_filtro_lista()
        self._on_search_ativos_debounced()

    def atualizar_resultados(self, resultados: list):
        # Congela colunas durante reset do modelo para evitar crash
        # se o usuário estiver arrastando uma coluna no momento do refresh
        header = self.table_view.horizontalHeader()
        was_blocked = header.signalsBlocked()
        header.blockSignals(True)
        was_movable = header.sectionsMovable()
        header.setSectionsMovable(False)
        try:
            self._dados_carregados = True
            self._resultados = resultados
            items = []
            for r in resultados:
                pior_b3 = r.pior_retorno - r.custo_b3
                pior_liquido = pior_b3 - r.custo_ir
                items.append({
                    "ativo": r.ativo,
                    "score": r.score,
                    "vencimento": r.vencimento,
                    "tipo_str": r.tipo.value,
                    "strike_put": r.strike_put,
                    "strike_call": r.strike_call,
                    "cod_put": r.cod_put,
                    "cod_call": r.cod_call,
                    "custo_liquido": r.custo_liquido,
                    "pior_retorno": r.pior_retorno,
                    "custo_b3": r.custo_b3,
                    "custo_ir": r.custo_ir,
                    "pior_b3": pior_b3,
                    "pior_liquido": pior_liquido,
                    "pct_cdi": r.pct_cdi,
                    "pct_cdi_melhor": r.pct_cdi_melhor,
                    "pct_cdi_liquido": r.pct_cdi_liquido,
                    "pct_cdi_melhor_liquido": r.pct_cdi_melhor_liquido,
                    "risco_str": r.risco_leilao.value,
                    "dias": r.dias,
                    "viavel": r.viavel,
                    "pop_upside": r.pop_upside,
                    "pop_downside": r.pop_downside,
                })

            self.model.atualizar(items)
        finally:
            header.setSectionsMovable(was_movable)
            header.blockSignals(was_blocked)

        ativos_atuais = set(
            self.lista_ativos.item(i).text()
            for i in range(1, self.lista_ativos.count())
        )
        novos_ativos = sorted(set(r.ativo for r in resultados if r.ativo not in ativos_atuais))
        if novos_ativos:
            whitelist = ler_whitelist_colar(self._db_path)
            usar_whitelist = bool(whitelist)
            self.lista_ativos.blockSignals(True)
            for ativo in novos_ativos:
                item = QListWidgetItem(ativo)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                if usar_whitelist:
                    item.setCheckState(Qt.Checked if ativo in whitelist else Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked)
                item.setForeground(QColor(Palette.TEXT_PRIMARY))
                self.lista_ativos.addItem(item)
            self.lista_ativos.blockSignals(False)

        self._aplicar_filtro_lista()

        if self.lista_ativos.count() == 0:
            todos_ativos = self._carregar_todos_ativos()
            if todos_ativos:
                self._popular_lista_ativos(todos_ativos)
            else:
                ativos_vistos = sorted(set(r.ativo for r in resultados))
                self._popular_lista_ativos(ativos_vistos)
        self.set_scan_completed(len(resultados), auto=self._auto_mode)
        self._atualizar_status()

        n_viaveis = sum(1 for r in resultados if r.viavel)
        if self._som_ativado and n_viaveis > 0:
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 150)

    def _abrir_regras(self):
        from src.ui.desktop.regras_dialog import RegrasDialog
        dlg = RegrasDialog("COLAR", self._db_path, self)
        dlg.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self.btn_regras.setVisible(not self.btn_regras.isVisible())
        else:
            super().keyPressEvent(event)

    def _toggle_som(self, ativo: bool):
        self._som_ativado = ativo
        self.btn_bell.setToolTip("Som: ligado" if ativo else "Som: desligado")
