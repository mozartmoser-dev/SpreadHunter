from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView,
    QMessageBox, QLabel, QHeaderView, QComboBox, QProgressBar
)
from PySide6.QtCore import Qt, QAbstractTableModel, QDate, QThread, Signal, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


class DividendosSortProxy(QSortFilterProxyModel):
    """Proxy que ordena datas ISO e numeros corretamente."""
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


class DividendosTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Tipo", "tipo"),
        ("Data COM", "data_com"),
        ("Data EX", "data_ex"),
        ("Pagamento", "data_pagamento"),
        ("Valor", "valor"),
        ("Atualizado", "atualizado_em"),
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
            if col_key in ("data_com", "data_ex", "data_pagamento", "atualizado_em"):
                return self._fmt_data(item.get(col_key))
            if col_key == "valor":
                val = item.get("valor")
                return "{:.6f}".format(val) if val else "-"
            return str(item.get(col_key, "-"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key == "valor":
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "ativo":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            if col_key == "valor":
                return QBrush(QColor(Palette.GREEN))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        if role == Qt.ItemDataRole.BackgroundRole:
            data_ex = item.get("data_ex")
            if data_ex:
                try:
                    dt = datetime.fromisoformat(str(data_ex)).date()
                    hoje = datetime.now().date()
                    if dt == hoje:
                        return QBrush(QColor("#2d4a1e"))
                    elif dt == hoje + timedelta(days=1):
                        return QBrush(QColor("#3d3a1e"))
                except ValueError:
                    pass
            return None

        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class DividendosFetchWorker(QThread):
    progresso = Signal(int, int, str)
    concluido = Signal(int, str)
    erro = Signal(str)

    def __init__(self, db_path, ativos: list[str], modo: str = "rapida"):
        super().__init__()
        self.db_path = db_path
        self.ativos = ativos
        self.modo = modo

    def run(self):
        try:
            from src.infrastructure.providers.dividendos_statusinvest import DividendosStatusInvestProvider
            from src.infrastructure.persistence.repositories.repositories import DividendoRepository

            provider = DividendosStatusInvestProvider()
            div_repo = DividendoRepository(self.db_path)

            total_proventos = 0
            total_ativos = len(self.ativos)

            for i, ativo in enumerate(self.ativos):
                self.progresso.emit(i + 1, total_ativos, ativo)

                dividendos = provider.buscar_proventos(ativo)

                if dividendos:
                    div_repo.save_batch(dividendos)
                    total_proventos += len(dividendos)

            msg = f"Atualizados {total_proventos} proventos para {total_ativos} ativos."
            self.concluido.emit(total_proventos, msg)
        except Exception as e:
            self.erro.emit(str(e))


class DividendosDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Agenda de Proventos")
        self.setMinimumSize(900, 500)
        self._setup_ui()
        self.carregar_dados()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_title = QLabel("Agenda de Proventos")
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
        self.cmb_filtro.addItem("Hoje")
        self.cmb_filtro.addItem("Amanhã")
        self.cmb_filtro.addItem("Próx. 7 dias")
        self.cmb_filtro.addItem("Próx. 30 dias")
        self.cmb_filtro.addItem("Ex-div recente")
        self.cmb_filtro.setStyleSheet("""
            QComboBox {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 130px;
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

        lbl_ordem = QLabel("Ordenar:")
        lbl_ordem.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        header_layout.addWidget(lbl_ordem)

        self.cmb_ordem = QComboBox()
        self.cmb_ordem.addItem("Data COM ↓", ("data_com", True))
        self.cmb_ordem.addItem("Data COM ↑", ("data_com", False))
        self.cmb_ordem.addItem("Data EX ↓", ("data_ex", True))
        self.cmb_ordem.addItem("Data EX ↑", ("data_ex", False))
        self.cmb_ordem.addItem("Ativo A-Z", ("ativo", False))
        self.cmb_ordem.addItem("Valor ↓", ("valor", True))
        self.cmb_ordem.setStyleSheet("""
            QComboBox {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 120px;
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
        self.cmb_ordem.currentIndexChanged.connect(self._aplicar_filtro)
        header_layout.addWidget(self.cmb_ordem)

        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_atualizar.setProperty("class", "primary")
        self.btn_atualizar.clicked.connect(self._atualizar_proventos)
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
        self.model = DividendosTableModel()

        self.proxy = DividendosSortProxy()
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
        header.resizeSection(0, 90)   # Ativo
        header.resizeSection(1, 120)  # Tipo
        header.resizeSection(2, 110)  # Data COM
        header.resizeSection(3, 110)  # Data EX
        header.resizeSection(4, 110)  # Pagamento
        header.resizeSection(5, 100)  # Valor
        # Atualizado fica elastico (StretchLastSection)
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def carregar_dados(self):
        from src.infrastructure.persistence.repositories.repositories import DividendoRepository
        repo = DividendoRepository(self.db_path)
        try:
            self._all_items = repo.get_all()
            self._aplicar_filtro()
        except Exception as e:
            QMessageBox.critical(self, "Erro", "Erro ao carregar dividendos: " + str(e))

    def _aplicar_filtro(self):
        if not hasattr(self, "_all_items"):
            return

        filtro = self.cmb_filtro.currentText()
        from datetime import date
        hoje = date.today()

        if filtro == "Hoje":
            filtrados = [d for d in self._all_items if d.get("data_ex") == hoje.isoformat()]
        elif filtro == "Amanhã":
            amanha = (hoje + timedelta(days=1)).isoformat()
            filtrados = [d for d in self._all_items if d.get("data_ex") == amanha]
        elif filtro == "Próx. 7 dias":
            fim = (hoje + timedelta(days=7)).isoformat()
            filtrados = [d for d in self._all_items if d.get("data_ex") and hoje.isoformat() <= d["data_ex"] <= fim]
        elif filtro == "Próx. 30 dias":
            fim = (hoje + timedelta(days=30)).isoformat()
            filtrados = [d for d in self._all_items if d.get("data_ex") and hoje.isoformat() <= d["data_ex"] <= fim]
        elif filtro == "Ex-div recente":
            inicio = self._recente_ex_div()
            filtrados = [d for d in self._all_items if d.get("data_ex") and inicio <= d["data_ex"] <= hoje.isoformat()]
        else:
            filtrados = self._all_items

        ordem = self.cmb_ordem.currentData()
        if ordem:
            chave, desc = ordem
            if chave == "valor":
                filtrados = sorted(filtrados, key=lambda d: d.get(chave, 0) or 0, reverse=desc)
            elif chave == "data_com":
                filtrados = sorted(filtrados, key=lambda d: str(d.get(chave, "") or ""), reverse=desc)
            else:
                filtrados = sorted(filtrados, key=lambda d: str(d.get(chave, "") or ""), reverse=desc)

        self.model.atualizar(filtrados)
        self.lbl_status.setText(f"{len(filtrados)} registros")

    @staticmethod
    def _recente_ex_div() -> str:
        """Início da janela de ex-div recente (últimos 5 dias úteis)."""
        from datetime import date
        from src.domain.services.calendario_b3 import eh_feriado
        dt = date.today()
        contados = 0
        while contados < 5:
            dt = dt - timedelta(days=1)
            if dt.weekday() >= 5 or eh_feriado(dt):
                continue
            contados += 1
        return dt.isoformat()

    def _atualizar_proventos(self):
        from src.infrastructure.persistence.repositories.repositories import (
            DividendoRepository, InstrumentoRepository
        )

        inst_repo = InstrumentoRepository(self.db_path)
        ativos = sorted(list(set(i.ativo for i in inst_repo.get_all() if i.ativo)))

        if not ativos:
            QMessageBox.warning(self, "Aviso", "Nenhum ativo na base. Importe a base de opções primeiro.")
            return

        self.btn_atualizar.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(ativos))
        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"Buscando proventos... (0/{len(ativos)})")

        self._worker = DividendosFetchWorker(self.db_path, ativos, "completa")
        self._worker.progresso.connect(self._on_progresso)
        self._worker.concluido.connect(self._on_concluido)
        self._worker.erro.connect(self._on_erro)
        self._worker.start()

    def _on_progresso(self, atual, total, ativo):
        self.progress_bar.setValue(atual)
        self.lbl_status.setText(f"Buscando {ativo}... ({atual}/{total})")

    def _on_concluido(self, total_proventos, msg):
        self.progress_bar.setVisible(False)
        self.btn_atualizar.setEnabled(True)
        self.lbl_status.setText(msg)
        self.carregar_dados()
        QMessageBox.information(self, "Sucesso", msg)

    def _on_erro(self, erro):
        self.progress_bar.setVisible(False)
        self.btn_atualizar.setEnabled(True)
        self.lbl_status.setText("Erro na atualização")
        QMessageBox.critical(self, "Erro", f"Erro ao atualizar:\n{erro}")
