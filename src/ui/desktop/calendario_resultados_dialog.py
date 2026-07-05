from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView,
    QMessageBox, QLabel, QHeaderView, QComboBox, QProgressBar
)
from PySide6.QtCore import Qt, QAbstractTableModel, QThread, Signal, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


class CalendarioSortProxy(QSortFilterProxyModel):
    def lessThan(self, left, right):
        src = self.sourceModel()
        l_val = src._items[left.row()].get(src.COLUMNS[left.column()][1])
        r_val = src._items[right.row()].get(src.COLUMNS[right.column()][1])
        if l_val is None:
            return True
        if r_val is None:
            return False
        if isinstance(l_val, (int, float)) and isinstance(r_val, (int, float)):
            return l_val < r_val
        return str(l_val) < str(r_val)


class CalendarioTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Empresa", "nome_empresa"),
        ("Data", "data_publicacao"),
        ("Trimestre", "trimestre_referencia"),
        ("Tipo", "tipo_documento"),
        ("Evento", "tipo_evento"),
        ("Fonte", "fonte"),
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
        return None

    @staticmethod
    def _fmt_data(val) -> str:
        if not val:
            return "-"
        try:
            if "T" in str(val):
                dt = datetime.fromisoformat(str(val))
                return dt.strftime("%d/%m/%Y")
            dt = datetime.fromisoformat(str(val))
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            return str(val)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key in ("data_publicacao",):
                return self._fmt_data(item.get(col_key))
            return str(item.get(col_key, "-"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "ativo":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            if col_key == "tipo_evento":
                val = item.get("tipo_evento", "")
                if val == "publicado":
                    return QBrush(QColor(Palette.GREEN))
                return QBrush(QColor("#f39c12"))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        if role == Qt.ItemDataRole.BackgroundRole:
            evento = item.get("tipo_evento", "")
            data_pub = item.get("data_publicacao")
            if evento == "previsto" and data_pub:
                try:
                    dt = datetime.fromisoformat(str(data_pub)).date()
                    hoje = datetime.now().date()
                    if dt == hoje:
                        return QBrush(QColor("#2d4a1e"))
                    elif timedelta(days=-3) <= (dt - hoje) <= timedelta(days=3):
                        pass
                except ValueError:
                    pass
            return None

        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class CalendarioFetchWorker(QThread):
    progresso = Signal(int, int, str)
    concluido = Signal(int, str)
    erro = Signal(str)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        try:
            from src.infrastructure.providers.calendario_resultados_webwallet import CalendarioResultadosWebwalletProvider
            from src.infrastructure.persistence.repositories.repositories import CalendarioResultadosRepository

            repo = CalendarioResultadosRepository(self.db_path)
            web = CalendarioResultadosWebwalletProvider()

            self.progresso.emit(1, 2, "Webwallet (previstos)...")
            previstos = web.buscar_todos()
            repo.delete_by_fonte("webwallet")
            repo.save_batch(previstos)

            self.progresso.emit(2, 2, "Finalizando...")
            msg = f"{len(previstos)} previstos"
            self.concluido.emit(len(previstos), msg)
        except Exception as e:
            self.erro.emit(str(e))


class CalendarioResultadosDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Agenda de Resultados")
        self.setMinimumSize(1000, 500)
        self._setup_ui()
        self.carregar_dados()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_title = QLabel("Agenda de Resultados (Balanços)")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        lbl_filtro = QLabel("Filtrar:")
        lbl_filtro.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        header_layout.addWidget(lbl_filtro)

        self.cmb_filtro = QComboBox()
        self.cmb_filtro.addItem("Todos")
        self.cmb_filtro.addItem("Previstos (próx. 60d)")
        self.cmb_filtro.addItem("Publicados")
        self.cmb_filtro.setStyleSheet("""
            QComboBox {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 140px;
                font-size: 9pt;
            }
            QComboBox::drop-down { border: 0; }
            QComboBox QAbstractItemView {
                background-color: #1e1e2f;
                color: #e0e0e0;
                selection-background-color: #2d2d44;
                selection-color: #1abc9c;
                border: 1px solid #2d2d44;
            }
        """)
        self.cmb_filtro.currentIndexChanged.connect(self._aplicar_filtro)
        header_layout.addWidget(self.cmb_filtro)

        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_atualizar.setProperty("class", "primary")
        self.btn_atualizar.clicked.connect(self._atualizar_resultados)
        header_layout.addWidget(self.btn_atualizar)

        layout.addLayout(header_layout)

        self.lbl_status = QLabel("0 registros")
        self.lbl_status.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e2f;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                height: 18px;
                text-align: center;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #1abc9c;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.table_view = QTableView()
        self.model = CalendarioTableModel()

        self.proxy = CalendarioSortProxy()
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

        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def carregar_dados(self):
        from src.infrastructure.persistence.repositories.repositories import CalendarioResultadosRepository
        repo = CalendarioResultadosRepository(self.db_path)
        try:
            self._all_items = repo.get_all()
            self._aplicar_filtro()
        except Exception as e:
            QMessageBox.critical(self, "Erro", "Erro ao carregar resultados: " + str(e))

    def _aplicar_filtro(self):
        if not hasattr(self, "_all_items"):
            return

        filtro = self.cmb_filtro.currentText()

        if filtro == "Previstos (próx. 60d)":
            from datetime import date
            hoje = date.today().isoformat()
            fim = (date.today() + timedelta(days=60)).isoformat()
            filtrados = [
                d for d in self._all_items
                if d.get("tipo_evento") == "previsto"
                and d.get("data_publicacao", "") >= hoje
                and d.get("data_publicacao", "") <= fim
            ]
        elif filtro == "Publicados":
            filtrados = [d for d in self._all_items if d.get("tipo_evento") == "publicado"]
        else:
            filtrados = self._all_items

        self.model.atualizar(filtrados)
        self.lbl_status.setText(f"{len(filtrados)} registros")

    def _atualizar_resultados(self):
        from src.infrastructure.persistence.repositories.repositories import CalendarioResultadosRepository
        repo = CalendarioResultadosRepository(self.db_path)

        self.btn_atualizar.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(2)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Buscando... (0/2)")

        self._worker = CalendarioFetchWorker(self.db_path)
        self._worker.progresso.connect(self._on_progresso)
        self._worker.concluido.connect(self._on_concluido)
        self._worker.erro.connect(self._on_erro)
        self._worker.start()

    def _on_progresso(self, atual, total, msg):
        self.progress_bar.setValue(atual)
        self.lbl_status.setText(f"{msg} ({atual}/{total})")

    def _on_concluido(self, total, msg):
        self.progress_bar.setVisible(False)
        self.btn_atualizar.setEnabled(True)
        self.lbl_status.setText(msg)
        self.carregar_dados()

    def _on_erro(self, erro):
        self.progress_bar.setVisible(False)
        self.btn_atualizar.setEnabled(True)
        self.lbl_status.setText("Erro na atualização")
        QMessageBox.critical(self, "Erro", f"Erro ao atualizar:\n{erro}")
