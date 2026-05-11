from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QSplitter, QToolBar,
    QAction, QTabWidget, QLabel, QFileDialog, QMessageBox,
    QHeaderView, QTableView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from src.infrastructure.persistence.database import get_db_path
from src.application.use_cases.importar_base import ImportarBaseUseCase
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.ui.desktop.import_dialog import ImportDialog
from src.ui.desktop.export_dialog import ExportDialog
from src.ui.desktop.parametros_widget import ParametrosWidget


class MainWindow(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.db_path = db_path or str(get_db_path())
        self.output_dir = str(Path("logs"))

        self.importar_uc = ImportarBaseUseCase(self.db_path)
        self.monitor_uc = MonitorOportunidadesUseCase(self.db_path)
        self.exportar_uc = ExportarOperacaoUseCase(self.db_path)

        self._rtd = RTDProfit()
        self._mercado_provider = MercadoDataProvider(self.db_path, self._rtd)
        self._dados_mercado: dict[str, dict] = {}
        self._setup_ui()
        self._setup_toolbar()
        self._setup_timer()

    def _setup_ui(self):
        self.setWindowTitle("SpreadHunter - Monitor de Oportunidades")
        self.setMinimumSize(1100, 650)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)

        self.table_model = MonitorTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSortingEnabled(False)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        font = QFont("Consolas", 9)
        self.table_view.setFont(font)

        splitter.addWidget(self.table_view)

        self.tabs = QTabWidget()
        self.parametros_widget = ParametrosWidget(self.db_path)
        self.tabs.addTab(self.parametros_widget, "Parametros")

        info_label = QLabel(
            "SpreadHunter v0.1\n\n"
            "1. Importe a base de instrumentos (XLSX)\n"
            "2. Configure os dados de mercado\n"
            "3. O monitor varre oportunidades\n"
            "4. Clique duplo em uma linha para exportar\n"
        )
        self.tabs.addTab(info_label, "Ajuda")

        splitter.addWidget(self.tabs)
        splitter.setSizes([750, 300])

        main_layout.addWidget(splitter)

        btn_layout = QHBoxLayout()

        self.btn_import = QPushButton("Importar Base")
        self.btn_import.clicked.connect(self._abrir_importacao)
        btn_layout.addWidget(self.btn_import)

        self.btn_varrer = QPushButton("Iniciar Monitor")
        self.btn_varrer.setCheckable(True)
        self.btn_varrer.setChecked(False)
        self.btn_varrer.clicked.connect(self._toggle_monitor)
        btn_layout.addWidget(self.btn_varrer)

        self.lbl_count = QLabel("0 oportunidades")
        btn_layout.addWidget(self.lbl_count)
        btn_layout.addStretch()

        main_layout.addLayout(btn_layout)

        self.statusBar().showMessage("Pronto — RTD: {}".format(
            "conectado" if self._rtd.disponivel else "indisponivel"
        ))

    def _setup_toolbar(self):
        toolbar = QToolBar("Arquivo")
        self.addToolBar(toolbar)

        action_import = QAction("Importar XLSX", self)
        action_import.triggered.connect(self._abrir_importacao)
        toolbar.addAction(action_import)

        action_varrer = QAction("Iniciar/Pausar", self)
        action_varrer.triggered.connect(lambda: self._toggle_monitor(not self.btn_varrer.isChecked()))
        toolbar.addAction(action_varrer)

        action_output = QAction("Pasta de Saida...", self)
        action_output.triggered.connect(self._selecionar_output_dir)
        toolbar.addAction(action_output)

    def _setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._varrer_oportunidades)

    def _toggle_monitor(self, checked):
        if checked:
            self.btn_varrer.setText("Pausar Monitor")
            self.btn_import.setEnabled(False)
            self.timer.start(1500)
            self._varrer_oportunidades()
            self.statusBar().showMessage("Monitor ativo — RTD: {}".format(
                "conectado" if self._rtd.disponivel else "indisponivel"
            ))
        else:
            self.btn_varrer.setText("Iniciar Monitor")
            self.btn_import.setEnabled(True)
            self.timer.stop()
            self.statusBar().showMessage("Monitor pausado")

    def _abrir_importacao(self):
        dialog = ImportDialog(self.importar_uc, self)
        dialog.exec_()
        if dialog.result is not None:
            self.statusBar().showMessage(
                "Importados {} instrumentos, {} ativos".format(
                    dialog.result.total_importados, len(dialog.result.ativos)
                )
            )
            if self.btn_varrer.isChecked():
                self._varrer_oportunidades()

    def _varrer_oportunidades(self):
        if self._rtd.disponivel:
            self._dados_mercado = self._mercado_provider.capturar_dados_mercado()

        resultados = self.monitor_uc.varrer(self._dados_mercado)
        self.table_model.atualizar(resultados)
        viaveis = sum(1 for r in resultados if r.viavel)
        self.lbl_count.setText(
            "{} oportunidades ({} viaveis)".format(len(resultados), viaveis)
        )
        self.statusBar().showMessage(
            "Varredura: {} oportunidades, {} viaveis".format(len(resultados), viaveis)
        )

    def _on_row_double_clicked(self, index):
        opp = self.table_model.get_oportunidade(index.row())
        if opp is None:
            return
        dialog = ExportDialog(opp, self.exportar_uc, self.output_dir, self)
        dialog.exec_()

    def _selecionar_output_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta de saida", self.output_dir,
        )
        if folder:
            self.output_dir = folder
            self.statusBar().showMessage("Pasta de saida: {}".format(folder))

    def set_dados_mercado(self, dados: dict[str, dict]):
        self._dados_mercado = dados

    def start_auto_scan(self, interval_ms: int = 5000):
        self.timer.start(interval_ms)

    def stop_auto_scan(self):
        self.timer.stop()
