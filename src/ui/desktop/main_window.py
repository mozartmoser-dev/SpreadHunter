from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QToolBar,
    QAction, QLabel, QDialog,
    QHeaderView, QTableView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from src.infrastructure.persistence.database import get_db_path
from src.application.use_cases.importar_base import ImportarBaseUseCase
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.ui.desktop.monitor_worker import MonitorWorker
from src.ui.desktop.import_dialog import ImportDialog
from src.ui.desktop.export_dialog import ExportDialog
from src.ui.desktop.parametros_widget import ParametrosWidget
from src.infrastructure.persistence.repositories.repositories import ParametroRepository


class MainWindow(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.db_path = db_path or str(get_db_path())
        self._last_scan_time = None
        self._total_opps = 0
        self._total_viaveis = 0

        self.importar_uc = ImportarBaseUseCase(self.db_path)
        self.exportar_uc = ExportarOperacaoUseCase(self.db_path)

        self._rtd = RTDProfit()
        self._worker = MonitorWorker(self.db_path, self._rtd)
        self._worker.oportunidades_atualizadas.connect(self._on_oportunidades_atualizadas)
        self._worker.status_message.connect(self._on_status_message)

        self._setup_ui()
        self._setup_toolbar()
        self._setup_status_bar()

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._update_scan_status)
        self._scan_timer.start(1000)

    def _setup_ui(self):
        self.setWindowTitle("SpreadHunter - Monitor de Oportunidades")
        self.setMinimumSize(1100, 650)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

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

        main_layout.addWidget(self.table_view)

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

    def _setup_toolbar(self):
        toolbar = QToolBar("Arquivo")
        self.addToolBar(toolbar)

        action_import = QAction("Importar XLSX", self)
        action_import.triggered.connect(self._abrir_importacao)
        toolbar.addAction(action_import)

        action_varrer = QAction("Iniciar/Pausar", self)
        action_varrer.triggered.connect(lambda: self._toggle_monitor(not self.btn_varrer.isChecked()))
        toolbar.addAction(action_varrer)

        action_parametros = QAction("Parametros", self)
        action_parametros.triggered.connect(self._abrir_parametros)
        toolbar.addAction(action_parametros)

    def _setup_status_bar(self):
        self._status_left = QLabel("Pronto")
        self._status_right = QLabel("")
        self._status_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusBar().addWidget(self._status_left, 1)
        self.statusBar().addPermanentWidget(self._status_right)
        self._update_cdi_display()

    def _update_cdi_display(self):
        param_repo = ParametroRepository(self.db_path)
        taxa_cdi = 0.0
        param = param_repo.get_by_chave("taxa_cdi")
        if param:
            taxa_cdi = param.valor
        cdi_anual_pct = taxa_cdi * 100
        cdi_mes = (1 + taxa_cdi) ** (1 / 12) - 1 if taxa_cdi > 0 else 0.0
        cdi_mes_pct = cdi_mes * 100
        cdi_dia = (1 + taxa_cdi) ** (1 / 365) - 1 if taxa_cdi > 0 else 0.0
        cdi_dia_pct = cdi_dia * 100
        self._status_right.setText(
            "CDI: {:.2f}%a | {:.4f}%m | {:.4f}%d".format(cdi_anual_pct, cdi_mes_pct, cdi_dia_pct)
        )

    def _abrir_parametros(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Parametros Operacionais")
        dialog.setMinimumSize(500, 600)
        layout = QVBoxLayout(dialog)
        widget = ParametrosWidget(self.db_path)
        layout.addWidget(widget)
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dialog.accept)
        layout.addWidget(btn_fechar)
        dialog.exec_()
        self._worker.recarregar_parametros()
        self._update_cdi_display()

    def _toggle_monitor(self, checked):
        if checked:
            self.btn_varrer.setText("Pausar Monitor")
            self.btn_import.setEnabled(False)
            if not self._worker.isRunning():
                self._worker.start()
            else:
                self._worker.retomar()
            self._status_left.setText("Monitor ativo — RTD: {}".format(
                "conectado" if self._rtd.disponivel else "indisponivel"
            ))
            self._update_cdi_display()
        else:
            self.btn_varrer.setText("Iniciar Monitor")
            self.btn_import.setEnabled(True)
            if self._worker.isRunning():
                self._worker.pausar()
            self._status_left.setText("Monitor pausado")

    def _on_oportunidades_atualizadas(self, resultados: list):
        self.table_model.atualizar(resultados)
        self._total_opps = len(resultados)
        self._total_viaveis = sum(1 for r in resultados if r.viavel)
        self.lbl_count.setText(
            "{} oportunidades ({} viaveis)".format(self._total_opps, self._total_viaveis)
        )
        self._last_scan_time = datetime.now()
        self._update_scan_status()

    def _on_status_message(self, msg: str):
        self._status_left.setText(msg)

    def _update_scan_status(self):
        if self._last_scan_time is None:
            return
        elapsed = (datetime.now() - self._last_scan_time).total_seconds()
        ts = self._last_scan_time.strftime("%H:%M:%S")
        rtd_status = "conectado" if self._rtd.disponivel else "indisponivel"
        self._status_left.setText(
            "Ultima varredura: {} ({}s atras) | {} oportunidades ({} viaveis) | RTD: {}".format(
                ts, int(elapsed), self._total_opps, self._total_viaveis, rtd_status
            )
        )

    def _abrir_importacao(self):
        dialog = ImportDialog(self.importar_uc, self)
        dialog.exec_()
        if dialog.result is not None:
            self._status_left.setText(
                "Importados {} instrumentos, {} ativos".format(
                    dialog.result.total_importados, len(dialog.result.ativos)
                )
            )

    def _on_row_double_clicked(self, index):
        opp = self.table_model.get_oportunidade(index.row())
        if opp is None:
            return
        dialog = ExportDialog(opp, self.exportar_uc, self)
        dialog.exec_()

    def closeEvent(self, event):
        self._worker.parar()
        super().closeEvent(event)

    def set_dados_mercado(self, dados: dict[str, dict]):
        pass

    def start_auto_scan(self, interval_ms: int = 1500):
        self._worker.set_interval(interval_ms)
        self.btn_varrer.setChecked(True)
        self._toggle_monitor(True)

    def stop_auto_scan(self):
        self.btn_varrer.setChecked(False)
        self._toggle_monitor(False)
