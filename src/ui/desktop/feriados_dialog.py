from datetime import date, datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView,
    QMessageBox, QLabel, QHeaderView, QComboBox, QProgressBar, QGroupBox,
    QFormLayout, QSpinBox, QFrame,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QThread, Signal, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


class FeriadosSortProxy(QSortFilterProxyModel):
    def lessThan(self, left, right):
        src = self.sourceModel()
        l_val = src._items[left.row()].get(src.COLUMNS[left.column()][1])
        r_val = src._items[right.row()].get(src.COLUMNS[right.column()][1])
        if l_val is None:
            return True
        if r_val is None:
            return False
        return str(l_val) < str(r_val)


class FeriadosTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Data", "data"),
        ("Feriado", "nome"),
        ("Tipo", "tipo"),
        ("Fonte", "fonte"),
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
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section][0]
        return None

    @staticmethod
    def _fmt_data(val) -> str:
        if not val:
            return "-"
        try:
            dt = datetime.fromisoformat(str(val).split("T")[0])
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            return str(val)

    def _fmt_tipo(self, val) -> str:
        labels = {"nacional": "Nacional", "estadual_sp": "SP (B3 fecha)"}
        return labels.get(str(val), str(val))

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key in ("data", "atualizado_em"):
                return self._fmt_data(item.get(col_key))
            if col_key == "tipo":
                return self._fmt_tipo(item.get(col_key))
            return str(item.get(col_key, "-"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "data":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            if col_key == "tipo" and str(item.get("tipo")) == "estadual_sp":
                return QBrush(QColor("#f39c12"))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        if role == Qt.ItemDataRole.BackgroundRole:
            try:
                dt = date.fromisoformat(str(item.get("data", "")))
                today = date.today()
                if dt == today:
                    return QBrush(QColor("#2d4a1e"))
            except (ValueError, TypeError):
                pass
            return None

        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class FeriadosFetchWorker(QThread):
    progresso = Signal(int, int, str)
    concluido = Signal(int, str)
    erro = Signal(str)

    def __init__(self, db_path, anos: list[int]):
        super().__init__()
        self.db_path = db_path
        self.anos = anos

    def run(self):
        try:
            from src.infrastructure.providers.feriados_b3_provider import FeriadosB3Provider
            from src.infrastructure.persistence.repositories.repositories import FeriadoB3Repository

            provider = FeriadosB3Provider()
            repo = FeriadoB3Repository(self.db_path)

            total = 0
            total_anos = len(self.anos)

            for i, ano in enumerate(self.anos):
                self.progresso.emit(i + 1, total_anos, str(ano))
                feriados = provider.buscar_feriados(ano)
                if feriados:
                    repo.delete_by_ano(ano)
                    repo.save_batch(feriados)
                    total += len(feriados)

            msg = f"Atualizados {total} feriados para {total_anos} ano(s)."
            self.concluido.emit(total, msg)
        except Exception as e:
            self.erro.emit(str(e))


class FeriadosDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Calendário B3 - Feriados")
        self.setMinimumSize(800, 500)
        self._setup_ui()
        self.carregar_dados()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_title = QLabel("Calendário B3 - Feriados")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        lbl_filtro = QLabel("Filtrar ano:")
        lbl_filtro.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        header_layout.addWidget(lbl_filtro)

        self.cmb_ano = QComboBox()
        self.cmb_ano.setStyleSheet("""
            QComboBox {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 100px;
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
        self.cmb_ano.addItem("Todos")
        self.cmb_ano.currentIndexChanged.connect(self._aplicar_filtro)
        header_layout.addWidget(self.cmb_ano)

        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_atualizar.setProperty("class", "primary")
        self.btn_atualizar.clicked.connect(self._atualizar_feriados)
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
        self.model = FeriadosTableModel()

        self.proxy = FeriadosSortProxy()
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
        header.resizeSection(0, 110)
        header.resizeSection(1, 280)
        header.resizeSection(2, 140)
        header.resizeSection(3, 100)
        layout.addWidget(self.table_view, stretch=1)

        cdi_group = QGroupBox("Calculadora CDI")
        cdi_group.setStyleSheet(f"""
            QGroupBox {{
                color: {Palette.TEXT_PRIMARY}; font-size: 10pt; font-weight: bold;
                border: 1px solid {Palette.BORDER}; border-radius: 6px;
                margin-top: 10px; padding-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }}
        """)
        cdi_layout = QFormLayout(cdi_group)
        cdi_layout.setSpacing(4)
        cdi_layout.setContentsMargins(10, 16, 10, 10)

        self._taxa_cdi = self._ler_taxa_cdi()
        taxa_label = QLabel(f"<b>{self._taxa_cdi * 100:.2f}% a.a.</b>")
        taxa_label.setStyleSheet(f"color: {Palette.YELLOW}; font-size: 10pt; font-family: Consolas;")
        cdi_layout.addRow("Taxa CDI:", taxa_label)

        self.spin_dc = QSpinBox()
        self.spin_dc.setRange(1, 3650)
        self.spin_dc.setValue(30)
        self.spin_dc.setStyleSheet(f"""
            QSpinBox {{
                background-color: #1e1e2f; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 2px 6px; font-size: 10pt; font-family: Consolas;
            }}
        """)
        self.spin_dc.valueChanged.connect(self._calcular_cdi)
        cdi_layout.addRow("Dias Corridos (DC):", self.spin_dc)

        self.lbl_du = QLabel("—")
        self.lbl_du.setStyleSheet(f"color: {Palette.CYAN}; font-size: 10pt; font-family: Consolas;")
        cdi_layout.addRow("Dias Úteis (DU):", self.lbl_du)

        self.lbl_cdi_dc = QLabel("—")
        self.lbl_cdi_dc.setStyleSheet(f"color: {Palette.GREEN}; font-size: 10pt; font-family: Consolas;")
        cdi_layout.addRow("CDI (DC/365):", self.lbl_cdi_dc)

        self.lbl_cdi_du = QLabel("—")
        self.lbl_cdi_du.setStyleSheet(f"color: {Palette.GREEN}; font-size: 10pt; font-family: Consolas;")
        cdi_layout.addRow("CDI (DU/252):", self.lbl_cdi_du)

        layout.addWidget(cdi_group)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

        self._calcular_cdi()

    def _ler_taxa_cdi(self) -> float:
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self.db_path)
        p = repo.get_by_chave("taxa_cdi")
        return p.valor if p else 0.1450

    def _calcular_cdi(self):
        from src.domain.services.calendario_b3 import dc_to_du_aproximado
        dc = self.spin_dc.value()
        du = dc_to_du_aproximado(dc)
        cdi_du = (1 + self._taxa_cdi) ** (du / 252) - 1
        cdi_dc = (1 + self._taxa_cdi) ** (dc / 365) - 1
        self.lbl_du.setText(str(du))
        self.lbl_cdi_dc.setText(f"{cdi_dc * 100:.4f}%")
        self.lbl_cdi_du.setText(f"{cdi_du * 100:.4f}%")

    def carregar_dados(self):
        from src.infrastructure.persistence.repositories.repositories import FeriadoB3Repository
        repo = FeriadoB3Repository(self.db_path)
        try:
            self._all_items = repo.get_all()
            self._preencher_cmb_anos(repo)
            self._aplicar_filtro()
        except Exception as e:
            QMessageBox.critical(self, "Erro", "Erro ao carregar feriados: " + str(e))

    def _preencher_cmb_anos(self, repo):
        anos = repo.get_anos_disponiveis()
        current = self.cmb_ano.currentText()
        self.cmb_ano.blockSignals(True)
        self.cmb_ano.clear()
        self.cmb_ano.addItem("Todos")
        for ano in anos:
            self.cmb_ano.addItem(str(ano))
        idx = self.cmb_ano.findText(current)
        if idx >= 0:
            self.cmb_ano.setCurrentIndex(idx)
        self.cmb_ano.blockSignals(False)

    def _aplicar_filtro(self):
        if not hasattr(self, "_all_items"):
            return
        filtro = self.cmb_ano.currentText()
        if filtro == "Todos":
            filtrados = self._all_items
        else:
            ano = int(filtro)
            filtrados = [f for f in self._all_items if str(f.get("data", "")).startswith(str(ano))]
        self.model.atualizar(filtrados)
        self.lbl_status.setText(f"{len(filtrados)} registros")

    def _atualizar_feriados(self):
        from src.infrastructure.persistence.repositories.repositories import FeriadoB3Repository

        repo = FeriadoB3Repository(self.db_path)
        anos_existentes = repo.get_anos_disponiveis()
        ano_corrente = date.today().year
        anos_alvo = sorted(set([ano_corrente - 1, ano_corrente, ano_corrente + 1] + anos_existentes))

        self.btn_atualizar.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(anos_alvo))
        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"Buscando feriados... (0/{len(anos_alvo)})")

        self._worker = FeriadosFetchWorker(self.db_path, anos_alvo)
        self._worker.progresso.connect(self._on_progresso)
        self._worker.concluido.connect(self._on_concluido)
        self._worker.erro.connect(self._on_erro)
        self._worker.start()

    def _on_progresso(self, atual, total, ano):
        self.progress_bar.setValue(atual)
        self.lbl_status.setText(f"Buscando {ano}... ({atual}/{total})")

    def _on_concluido(self, total_feriados, msg):
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
