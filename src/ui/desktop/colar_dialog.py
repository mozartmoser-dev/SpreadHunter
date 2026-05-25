from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QLineEdit, QFormLayout, QFrame,
    QListWidget, QListWidgetItem, QWidget, QTextEdit,
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, QStringListModel, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


CLASSIF_CORES = {
    "Tradicional": QColor("#1abc9c"),
    "Strikes Abaixo": QColor("#9b59b6"),
    "Strikes Acima": QColor("#e67e22"),
}

RISCO_CORES = {
    "Baixo": QBrush(QColor(Palette.GREEN)),
    "Médio": QBrush(QColor(Palette.ORANGE)),
    "Alto": QBrush(QColor(Palette.RED)),
}


class ColarTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Vencimento", "vencimento"),
        ("Tipo", "tipo_str"),
        ("K Put", "strike_put"),
        ("K Call", "strike_call"),
        ("Cód Put", "cod_put"),
        ("Cód Call", "cod_call"),
        ("Custo Liq", "custo_liquido"),
        ("Pior Ret", "pior_retorno"),
        ("% CDI", "pct_cdi"),
        ("Risco", "risco_str"),
        ("Dias", "dias"),
    ]

    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and 0 <= section < len(self.COLUMNS):
            if role == Qt.DisplayRole:
                return self.COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.DisplayRole:
            val = item.get(col_key)
            if val is None:
                return "-"
            if col_key in ("strike_put", "strike_call", "custo_liquido", "pior_retorno"):
                return "R$ {:.2f}".format(val)
            if col_key == "pct_cdi":
                return "{:.2f}x".format(val)
            if col_key == "vencimento":
                if hasattr(val, "strftime"):
                    return val.strftime("%d/%m/%Y")
                return str(val)
            return str(val)

        if role == Qt.ForegroundRole:
            if col_key == "tipo_str":
                tipo = item.get("tipo_str", "")
                cor = CLASSIF_CORES.get(tipo)
                if cor:
                    return QBrush(cor)
                return QBrush(QColor(Palette.TEXT_PRIMARY))
            if col_key == "risco_str":
                risco = item.get("risco_str", "")
                return RISCO_CORES.get(risco, QBrush(QColor(Palette.TEXT_MUTED)))
            if col_key == "pct_cdi":
                return QBrush(QColor(Palette.YELLOW))
            if col_key in ("strike_put", "strike_call", "custo_liquido", "pior_retorno"):
                return QBrush(QColor(Palette.TEXT_PRIMARY))
            return QBrush(QColor(Palette.TEXT_MUTED))

        if role == Qt.TextAlignmentRole:
            center_cols = {"strike_put", "strike_call", "custo_liquido", "pior_retorno", "pct_cdi", "risco_str", "dias"}
            if col_key in center_cols:
                return Qt.AlignCenter | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.BackgroundRole:
            if not item.get("viavel", False):
                return QBrush(QColor(Palette.ROW_NOT_VIABLE))
            return None

        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class ColarSortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtro_ativo = ""
        self._filtro_lista = None

    def set_filtro_ativo(self, texto: str):
        self._filtro_ativo = texto.strip().upper()
        self._filtro_lista = None
        self.invalidateFilter()

    def set_filtro_lista(self, ativos: set):
        self._filtro_lista = ativos
        self._filtro_ativo = ""
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        src = self.sourceModel()
        idx = src.index(row, 0)
        ativo = src.data(idx, Qt.DisplayRole) or ""

        if self._filtro_lista is not None:
            return ativo in self._filtro_lista
        if self._filtro_ativo:
            return self._filtro_ativo in ativo.upper()
        return True


class ColarDialog(QDialog):
    iniciar_scan_signal = pyqtSignal()
    parar_scan_signal = pyqtSignal()
    selecao_alterada = pyqtSignal(list)

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("🛡 Monitor de Colares Protetivos")
        self.setMinimumSize(1000, 500)
        self._resultados = []
        self._db_path = db_path
        self._scanning = False
        self._auto_mode = False
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

        self.lbl_scan_status = QLabel("✅ Pronto")
        self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt;")
        left_panel.addWidget(self.lbl_scan_status)

        body_layout.addWidget(left_widget)

        self.table_view = QTableView()
        self.model = ColarTableModel()

        self.proxy = ColarSortProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)

        self.table_view.setModel(self.proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 9))
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().hide()

        header = self.table_view.horizontalHeader()
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
        self.btn_scan.setEnabled(not todos_marcados and n_sel > 0 and not self._scanning)
        self.selecao_alterada.emit(selecionados if not todos_marcados else [])
        self._atualizar_status()

    def _atualizar_status(self):
        total = self.proxy.rowCount()
        filtro = self.txt_filtro.text().strip()
        rtd_str = "RTD: ON" if getattr(self, "_rtd_ok", False) else "RTD: ---"
        if total == 0 and filtro:
            self.lbl_status.setText(f"Nenhum colar para '{filtro}' | {rtd_str}")
        elif total == 0:
            self.lbl_status.setText(f"Aguardando dados... | {rtd_str}")
        elif filtro:
            self.lbl_status.setText(f"{total} colares para '{filtro}' | {rtd_str}")
        else:
            self.lbl_status.setText(f"{total} colares viáveis | {rtd_str}")

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
        val = QLabel(f"{r.ativo} à vista — R$ {r.preco_ativo:.2f}")
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
        val.setStyleSheet(f"color: {Palette.YELLOW}; font-size: 11pt; font-weight: bold; font-family: Consolas;")
        form.addRow(lbl, val)

        lbl = QLabel("Pior Retorno:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"R$ {r.pior_retorno:.2f} ({r.pct_ganho*100:.2f}% / {r.pct_cdi:.2f}x CDI)")
        val.setStyleSheet(value_style)
        form.addRow(lbl, val)

        val_color = Palette.GREEN if r.pct_cdi >= 1.0 else Palette.RED
        lbl = QLabel("Pior caso vs CDI:")
        lbl.setStyleSheet(label_style)
        val = QLabel(f"{'✅ Paga CDI+' if r.viavel else '❌ Abaixo do CDI'}")
        val.setStyleSheet(f"color: {val_color}; font-size: 10pt; font-weight: bold;")
        form.addRow(lbl, val)

        lbl = QLabel("Risco de Leilão:")
        lbl.setStyleSheet(label_style)
        risco_color = Palette.GREEN if r.risco_leilao.value == "Baixo" else (Palette.ORANGE if r.risco_leilao.value == "Médio" else Palette.RED)
        val = QLabel(r.risco_leilao.value)
        val.setStyleSheet(f"color: {risco_color}; font-size: 10pt; font-weight: bold;")
        form.addRow(lbl, val)

        layout.addLayout(form)
        layout.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        layout.addWidget(btn_fechar, alignment=Qt.AlignRight)

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
        self.lista_ativos.blockSignals(True)
        self.lista_ativos.clear()

        item_todos = QListWidgetItem("TODOS")
        item_todos.setFlags(item_todos.flags() & ~Qt.ItemIsUserCheckable)
        item_todos.setForeground(QColor(Palette.YELLOW))
        item_todos.setToolTip("Mostrar todos os ativos")
        font_todos = QFont()
        font_todos.setBold(True)
        item_todos.setFont(font_todos)
        self.lista_ativos.addItem(item_todos)

        for ativo in ativos:
            item = QListWidgetItem(ativo)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setForeground(QColor(Palette.TEXT_PRIMARY))
            self.lista_ativos.addItem(item)

        self.lista_ativos.blockSignals(False)
        self._aplicar_filtro_lista()
        self._on_search_ativos_debounced()

    def atualizar_resultados(self, resultados: list):
        self._resultados = resultados
        items = []
        for r in resultados:
            items.append({
                "ativo": r.ativo,
                "vencimento": r.vencimento,
                "tipo_str": r.tipo.value,
                "strike_put": r.strike_put,
                "strike_call": r.strike_call,
                "cod_put": r.cod_put,
                "cod_call": r.cod_call,
                "custo_liquido": r.custo_liquido,
                "pior_retorno": r.pior_retorno,
                "pct_cdi": r.pct_cdi,
                "risco_str": r.risco_leilao.value,
                "dias": r.dias,
                "viavel": r.viavel,
            })

        self.model.atualizar(items)

        if self._auto_mode:
            self.proxy.set_filtro_ativo("")

        if self.lista_ativos.count() == 0:
            todos_ativos = self._carregar_todos_ativos()
            if todos_ativos:
                self._popular_lista_ativos(todos_ativos)
            else:
                ativos_vistos = sorted(set(r.ativo for r in resultados))
                self._popular_lista_ativos(ativos_vistos)
        self.set_scan_completed(len(resultados), auto=self._auto_mode)
        self._atualizar_status()
