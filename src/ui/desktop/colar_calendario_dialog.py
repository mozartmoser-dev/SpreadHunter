from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QLineEdit, QFormLayout, QFrame,
    QListWidget, QListWidgetItem, QWidget, QTextEdit,
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


class ColarCalTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Venc Call", "vencimento_call"),
        ("Venc Put", "vencimento_put"),
        ("K Call", "strike_call"),
        ("K Put", "strike_put"),
        ("Cód Call", "cod_call"),
        ("Cód Put", "cod_put"),
        ("IV Call", "iv_call"),
        ("IV Put", "iv_put"),
        ("Prêmio Call", "premio_call"),
        ("Prêmio Put", "premio_put"),
        ("Crédito", "net_credito"),
        ("θ Call", "theta_call"),
        ("θ Put", "theta_put"),
        ("θ Líq", "theta_liquido"),
        ("P Put VC", "valor_put_venc_call"),
        ("PNL Proj", "pnl_projetado"),
        ("% CDI", "pct_cdi"),
        ("Tipo", "tipo_str"),
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
            if col_key in ("strike_call", "strike_put", "premio_call", "premio_put",
                           "net_credito", "valor_put_venc_call", "pnl_projetado"):
                return f"R$ {val:.2f}"
            if col_key in ("pct_cdi",):
                return f"{val:.2f}x"
            if col_key in ("iv_call", "iv_put"):
                return f"{val:.1f}%"
            if col_key in ("theta_call", "theta_put", "theta_liquido"):
                if val == 0:
                    return "-"
                return f"{val:.2f}"
            if col_key in ("pct_retorno",):
                return f"{val:.2f}%"
            if col_key in ("vencimento_call", "vencimento_put"):
                if hasattr(val, "strftime"):
                    return val.strftime("%d/%m")
                return str(val)
            return str(val)
        if role == Qt.ForegroundRole:
            if col_key == "tipo_str":
                tipo = item.get("tipo_str", "")
                cores = {"Alta": QColor("#2ecc71"), "Baixa": QColor("#e74c3c"), "Neutro": QColor("#f39c12")}
                return QBrush(cores.get(tipo, QColor(Palette.TEXT_PRIMARY)))
            if col_key == "pct_cdi":
                return QBrush(QColor(Palette.YELLOW))
            if col_key in ("theta_liquido",):
                val = item.get("theta_liquido", 0)
                if val > 0:
                    return QBrush(QColor(Palette.GREEN))
                return QBrush(QColor(Palette.RED))
            return QBrush(QColor(Palette.TEXT_MUTED))
        if role == Qt.TextAlignmentRole:
            center_cols = {"strike_call", "strike_put", "premio_call", "premio_put", "net_credito",
                           "iv_call", "iv_put", "theta_call", "theta_put", "theta_liquido",
                           "pct_cdi", "pnl_projetado", "tipo_str", "valor_put_venc_call"}
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


class ColarCalSortProxy(QSortFilterProxyModel):
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


class ColarCalendarioDialog(QDialog):
    iniciar_scan_signal = pyqtSignal(list)
    parar_scan_signal = pyqtSignal()
    selecao_alterada = pyqtSignal(list)

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("📅 Monitor de Collar Calendário")
        self.setMinimumSize(1200, 550)
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

        lbl_title = QLabel("Collar Calendário")
        lbl_title.setStyleSheet(
            f"font-size: 13pt; font-weight: bold; color: {Palette.TEXT_PRIMARY}; padding: 4px 0;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        self.lbl_status = QLabel("0 oportunidades")
        self.lbl_status.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 9pt;")
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
        lbl_filtro.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 9pt; font-weight: bold;")
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
            QLineEdit:focus { border-color: #f39c12; }
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
                color: #f39c12;
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
            QPushButton:hover { background-color: #2d2d44; color: #f39c12; }
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
                background-color: #f39c12; color: #0d0d1a;
                border: none; border-radius: 4px;
                padding: 6px; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #e67e22; }
            QPushButton:disabled { background-color: #2d2d44; color: #666; }
        """)
        self.btn_scan.clicked.connect(self._toggle_scan)
        left_panel.addWidget(self.btn_scan)

        self.lbl_scan_status = QLabel("✅ Pronto")
        self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt;")
        left_panel.addWidget(self.lbl_scan_status)

        body_layout.addWidget(left_widget)

        self.table_view = QTableView()
        self.model = ColarCalTableModel()

        self.proxy = ColarCalSortProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.proxy.sort(17, Qt.DescendingOrder)

        self.table_view.setModel(self.proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 8))
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.verticalHeader().setDefaultSectionSize(24)
        self.table_view.verticalHeader().hide()

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
        self._todos_ativos_lista = todos_ativos
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
        if total == 0 and filtro:
            self.lbl_status.setText(f"Nenhum collar para '{filtro}'")
        elif total == 0:
            self.lbl_status.setText("Aguardando dados...")
        elif filtro:
            self.lbl_status.setText(f"{total} oportunidades para '{filtro}'")
        else:
            self.lbl_status.setText(f"{total} oportunidades viáveis")

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
                    background-color: #f39c12; color: #0d0d1a;
                    border: none; border-radius: 4px;
                    padding: 6px; font-size: 9pt; font-weight: bold;
                }
                QPushButton:hover { background-color: #e67e22; }
                QPushButton:disabled { background-color: #2d2d44; color: #666; }
            """)
            self.btn_scan.setEnabled(True)
            self.lbl_scan_status.setText("⏹ Scanner parado")
            self.lbl_scan_status.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 8pt;")
            self._aplicar_filtro_lista()
            self.parar_scan_signal.emit()
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
            selecionados = [self.lista_ativos.item(i).text()
                             for i in range(1, self.lista_ativos.count())
                             if self.lista_ativos.item(i).checkState() == Qt.Checked]
            self.iniciar_scan_signal.emit(selecionados)

    def set_scan_completed(self, n_resultados: int, auto: bool = False):
        if auto and self._auto_mode:
            self._scanning = False
            self.btn_scan.setEnabled(True)
            if n_resultados > 0:
                self.lbl_scan_status.setText(f"🔄 Scanner ligado | {n_resultados} oportunidades")
            else:
                self.lbl_scan_status.setText("🔄 Scanner ligado (a cada ~60s)")
            self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt; font-weight: bold;")
        else:
            self._scanning = False
            self.btn_scan.setEnabled(True)
            if n_resultados > 0:
                self.lbl_scan_status.setText(f"✅ {n_resultados} oportunidades encontradas")
                self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt; font-weight: bold;")
            else:
                self.lbl_scan_status.setText("✅ Nenhuma oportunidade viável")
                self.lbl_scan_status.setStyleSheet(f"color: {Palette.TEXT_MUTED}; font-size: 8pt;")

    def _on_row_double_clicked(self, index):
        proxy_idx = self.proxy.mapToSource(index)
        row = proxy_idx.row()
        if row < 0 or row >= len(self._resultados):
            return
        r = self._resultados[row]
        self._mostrar_detalhes(r)

    def _mostrar_detalhes(self, r):
        from src.domain.services.calculadora_colar_calendario import ResultadoColarCalendario

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Collar Calendário — {r.ativo}")
        dialog.setMinimumSize(520, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"<b>{r.ativo}</b> — Collar Calendário {r.tipo.value}")
        title.setStyleSheet(f"font-size: 14pt; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(6)
        label_style = f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;"
        value_style = f"color: {Palette.TEXT_PRIMARY}; font-size: 10pt; font-family: Consolas;"

        def add_row(nome, valor, cor=None):
            lbl = QLabel(nome)
            lbl.setStyleSheet(label_style)
            val = QLabel(valor)
            style = value_style
            if cor:
                style += f"; color: {cor};"
            val.setStyleSheet(style)
            form.addRow(lbl, val)

        add_row("Preço Ativo:", f"R$ {r.preco_ativo:.2f}")
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep2)

        add_row("Vender CALL:", f"{r.cod_call} K={r.strike_call:.2f} — R$ {r.premio_call:.2f}")
        add_row("Vencimento Call:", r.vencimento_call.strftime("%d/%m/%Y") if hasattr(r.vencimento_call, "strftime") else str(r.vencimento_call))
        add_row("DTE Call:", f"{r.dte_call} dias")
        add_row("IV Call:", f"{r.iv_call:.1f}%")
        add_row("Theta Call:", f"{r.theta_call:.3f} por dia")

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep3)

        add_row("Comprar PUT:", f"{r.cod_put} K={r.strike_put:.2f} — R$ {r.premio_put:.2f}")
        add_row("Vencimento Put:", r.vencimento_put.strftime("%d/%m/%Y") if hasattr(r.vencimento_put, "strftime") else str(r.vencimento_put))
        add_row("DTE Put:", f"{r.dte_put} dias (+{r.dte_extra}d extra)")
        add_row("IV Put:", f"{r.iv_put:.1f}%")
        add_row("Theta Put:", f"{r.theta_put:.3f} por dia")

        sep4 = QFrame()
        sep4.setFrameShape(QFrame.HLine)
        sep4.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        form.addRow(sep4)

        add_row("Crédito Líquido:", f"R$ {r.net_credito:.2f}", cor=Palette.YELLOW)
        add_row("Theta Líquido:", f"{r.theta_liquido:.3f} por dia",
                cor=Palette.GREEN if r.theta_liquido > 0 else Palette.RED)
        add_row("Valor Put no VC Call:", f"R$ {r.valor_put_venc_call:.2f}", cor=Palette.CYAN)
        add_row("PNL Projetado:", f"R$ {r.pnl_projetado:.2f} ({r.pct_retorno:.2f}%)")
        add_row("% CDI:", f"{r.pct_cdi:.2f}x",
                cor=Palette.GREEN if r.pct_cdi >= 1.0 else Palette.RED)

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
        btn_row.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)

        layout.addLayout(btn_row)
        dialog.exec_()

    def _plot_payoff(self, r):
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        S = r.preco_ativo
        Kc = r.strike_call
        Kp = r.strike_put
        Pc = r.premio_call
        Pp = r.premio_put

        x_min = min(Kp, S) * 0.85
        x_max = max(Kc, S) * 1.15
        x = np.linspace(x_min, x_max, 500)

        d1 = (np.log(x / Kc) + (0.1325 + 0.5 * (r.iv_call / 100) ** 2) * (r.dte_call / 365)) / ((r.iv_call / 100) * np.sqrt(r.dte_call / 365))
        d2 = d1 - (r.iv_call / 100) * np.sqrt(r.dte_call / 365)
        call_val = x * norm.cdf(d1) - Kc * np.exp(-0.1325 * r.dte_call / 365) * norm.cdf(d2)

        Tp = r.dte_put / 365
        dp1 = (np.log(x / Kp) + (0.1325 + 0.5 * (r.iv_put / 100) ** 2) * Tp) / ((r.iv_put / 100) * np.sqrt(Tp))
        dp2 = dp1 - (r.iv_put / 100) * np.sqrt(Tp)
        put_val = Kp * np.exp(-0.1325 * Tp) * norm.cdf(-dp2) - x * norm.cdf(-dp1)

        pnl = Pc - call_val + put_val - Pp

        BG = '#0d0d0d'; TEXT = '#c0c0c0'; RED = '#ff3355'
        ACCENT = '#ffc107'; FILL_BLUE = '#1a5276'

        fig = Figure(figsize=(7, 4), facecolor=BG)
        ax = fig.add_subplot(111, facecolor=BG)

        ax.plot(x, pnl, color=ACCENT, linewidth=2.0, label='Payoff')

        ax.axhline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.3)
        ax.axvline(S, color='#2196f3', linewidth=0.7, linestyle='--', alpha=0.8, label='Entrada')
        ax.axvline(Kp, color=RED, linewidth=0.7, linestyle='--', alpha=0.8, label=f'K Put {Kp:.2f}')
        ax.axvline(Kc, color=ACCENT, linewidth=0.7, linestyle='--', alpha=0.8, label=f'K Call {Kc:.2f}')

        ax.fill_between(x, 0, pnl, where=(pnl >= 0), color=FILL_BLUE, alpha=0.12)
        ax.fill_between(x, 0, pnl, where=(pnl < 0), color=RED, alpha=0.1)

        ax.set_xlabel('Preço do Ativo no Vencimento da Call (R$)', color=TEXT, fontsize=9)
        ax.set_ylabel('Lucro / Prejuízo (R$)', color=TEXT, fontsize=9)
        ax.set_title(f'Payoff Collar Calendário — {r.ativo}', color='#e0e0e0', fontsize=11, fontweight='bold')

        ax.tick_params(colors=TEXT, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#333')
        ax.legend(loc='best', fontsize=7, labelcolor=TEXT, facecolor='#1a1a1a', edgecolor='#333')

        fig.tight_layout()

        payoff_dialog = QDialog(self, Qt.Window)
        payoff_dialog.setWindowTitle(f"Payoff Calendário — {r.ativo}")
        payoff_dialog.setMinimumSize(750, 480)
        payoff_layout = QVBoxLayout(payoff_dialog)
        payoff_layout.setContentsMargins(8, 8, 8, 8)
        canvas = FigureCanvas(fig)
        payoff_layout.addWidget(canvas)
        btn_close = QPushButton("Fechar")
        btn_close.setAutoDefault(False)
        btn_close.clicked.connect(payoff_dialog.close)
        payoff_layout.addWidget(btn_close, alignment=Qt.AlignRight)
        payoff_dialog.exec_()

    def _carregar_todos_ativos(self) -> list[str]:
        if not self._db_path:
            return []
        try:
            from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
            repo = InstrumentoRepository(self._db_path)
            inst_map = repo.get_all_mapped()
            ativos = sorted(set(inst.ativo for inst in inst_map.values() if inst.ativo))
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
                "vencimento_call": r.vencimento_call,
                "vencimento_put": r.vencimento_put,
                "strike_call": r.strike_call,
                "strike_put": r.strike_put,
                "cod_call": r.cod_call,
                "cod_put": r.cod_put,
                "iv_call": r.iv_call,
                "iv_put": r.iv_put,
                "premio_call": r.premio_call,
                "premio_put": r.premio_put,
                "net_credito": r.net_credito,
                "theta_call": r.theta_call,
                "theta_put": r.theta_put,
                "theta_liquido": r.theta_liquido,
                "valor_put_venc_call": r.valor_put_venc_call,
                "pnl_projetado": r.pnl_projetado,
                "pct_retorno": r.pct_retorno,
                "pct_cdi": r.pct_cdi,
                "tipo_str": r.tipo.value,
                "viavel": r.viavel,
            })
        self.model.atualizar(items)
        if self._auto_mode:
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
