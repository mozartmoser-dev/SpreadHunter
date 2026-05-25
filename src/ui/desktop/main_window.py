import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QToolBar, QAction, QLabel, QDialog,
    QHeaderView, QTableView, QAbstractItemView, QFrame, QMenu,
    QCheckBox, QComboBox,
)
from PyQt5.QtCore import Qt, QTimer, QSize, QProcess
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QPixmap, QPainter

from src.infrastructure.persistence.database import get_db_path
from src.application.use_cases.importar_base import ImportarBaseUseCase
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.ui.desktop.theme import DARK_THEME_QSS, Palette, get_theme_qss
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.ui.desktop.monitor_worker import MonitorWorker
from src.ui.desktop.import_dialog import ImportDialog
from src.ui.desktop.export_dialog import ExportDialog
from src.ui.desktop.parametros_widget import ParametrosWidget
from src.ui.desktop.engine_dashboard import EngineDashboard
from src.ui.desktop.colar_dialog import ColarDialog
from src.ui.desktop.colar_calendario_dialog import ColarCalendarioDialog
from src.infrastructure.persistence.repositories.repositories import ParametroRepository


def _make_led_icon(color_hex: str, size: int = 12) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor(color_hex)))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.db_path = db_path or str(get_db_path())
        self._last_scan_time = None
        self._total_opps = 0
        self._total_viaveis = 0
        self._resultados_brutos = []
        self._ultimos_colares = []
        self._ultimos_colares_cal = []

        self.importar_uc = ImportarBaseUseCase(self.db_path)
        self.exportar_uc = ExportarOperacaoUseCase(self.db_path)

        self._rtd_connected = False
        self._worker = MonitorWorker(self.db_path, None)
        self._worker.oportunidades_atualizadas.connect(self._on_oportunidades_atualizadas)
        self._worker.status_message.connect(self._on_status_message)
        self._worker.rtd_status.connect(self._on_rtd_status)
        self._worker.engine_stats_updated.connect(self._on_engine_stats_updated)
        self._worker.colares_atualizados.connect(self._on_colares_atualizados)

        self._worker.colares_calendario_atualizados.connect(self._on_colares_calendario_atualizados)

        self._engine_dialog = EngineDashboard(self)
        self._colar_dialog = None
        self._colar_cal_dialog = None

        self._aplicar_tema_configurado()

        self._setup_ui()
        self._setup_toolbar()
        self._setup_status_bar()

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._update_scan_status)
        self._scan_timer.start(1000)
        self._refresh_ativos_filter()

    def _setup_ui(self):
        self.setWindowTitle("SpreadHunter — Monitor de Oportunidades")
        self.setMinimumSize(1200, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(8)

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
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self._show_column_menu)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().hide()
        self.table_view.setShowGrid(True)
        self._apply_hidden_columns()

        from src.ui.desktop.badge_delegate import BadgeDelegate
        delegate = BadgeDelegate(self.table_view)
        for idx, (col_name, col_key) in enumerate(MonitorTableModel.COLUMNS):
            if col_key in ("label_tipo", "liq_indicator"):
                self.table_view.setItemDelegateForColumn(idx, delegate)

        font = QFont("Consolas", 9)
        self.table_view.setFont(font)

        main_layout.addWidget(self.table_view, stretch=1)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #2d2d44; max-height: 1px;")
        main_layout.addWidget(separator)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_import = QPushButton("📥  Importar Base")
        self.btn_import.setProperty("class", "primary")
        self.btn_import.clicked.connect(self._abrir_importacao)
        btn_layout.addWidget(self.btn_import)

        self.btn_importflash = QPushButton("⚡  ImportFlash")
        self.btn_importflash.clicked.connect(self._abrir_importflash)
        self.btn_importflash.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a3a5c; color: {Palette.TEXT_PRIMARY};
                border: 1px solid #2c6fbb; border-radius: 4px;
                padding: 6px 12px; font-size: 9pt; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #204a77; }}
        """)
        btn_layout.addWidget(self.btn_importflash)

        self.btn_historico = QPushButton("📊  Histórico")
        self.btn_historico.clicked.connect(self._abrir_historico)
        btn_layout.addWidget(self.btn_historico)

        self.btn_dividendos = QPushButton("📅  Proventos")
        self.btn_dividendos.clicked.connect(self._abrir_dividendos)
        btn_layout.addWidget(self.btn_dividendos)

        self.btn_colar = QPushButton("🛡  Colares")
        self.btn_colar.clicked.connect(self._abrir_colar)
        btn_layout.addWidget(self.btn_colar)

        self.btn_colar_cal = QPushButton("📅  Collar Cal")
        self.btn_colar_cal.clicked.connect(self._abrir_colar_calendario)
        self.btn_colar_cal.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d1f0e; color: {Palette.TEXT_PRIMARY};
                border: 1px solid #f39c12; border-radius: 4px;
                padding: 6px 12px; font-size: 9pt; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3d2f1e; }}
        """)
        btn_layout.addWidget(self.btn_colar_cal)

        self.btn_varrer = QPushButton("▶  Iniciar Monitor")
        self.btn_varrer.setCheckable(True)
        self.btn_varrer.setChecked(False)
        self.btn_varrer.setProperty("class", "success")
        self.btn_varrer.clicked.connect(self._toggle_monitor)
        btn_layout.addWidget(self.btn_varrer)

        btn_layout.addSpacing(16)

        self.chk_tp_op = QCheckBox("Exibir Todas Operações")
        self.chk_tp_op.setChecked(False)
        self.chk_tp_op.setStyleSheet(
            "QCheckBox {{ color: {}; spacing: 4px; font-size: 9pt; }}"
            "QCheckBox::indicator {{ width: 14px; height: 14px; }}".format(Palette.TEXT_MUTED)
        )
        self.chk_tp_op.toggled.connect(self._on_tp_op_toggled)
        btn_layout.addWidget(self.chk_tp_op)

        self.lbl_count = QLabel("0 oportunidades | 0 viaveis")
        self.lbl_count.setStyleSheet(
            "color: {}; font-size: 10pt; font-weight: bold; padding: 0 8px;".format(Palette.TEXT_SECONDARY)
        )
        btn_layout.addWidget(self.lbl_count)

        self._status_colar = QLabel("")
        self._status_colar.setStyleSheet("color: {}; font-size: 10pt; font-weight: bold; padding: 0 8px;".format(Palette.GREEN))
        btn_layout.addWidget(self._status_colar)

        self._status_colar_cal = QLabel("")
        self._status_colar_cal.setStyleSheet("color: {}; font-size: 10pt; font-weight: bold; padding: 0 8px;".format(Palette.YELLOW))
        btn_layout.addWidget(self._status_colar_cal)

        btn_layout.addSpacing(16)

        self.lbl_filter_ativo = QLabel("Filtrar Ativo:")
        self.lbl_filter_ativo.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED))
        btn_layout.addWidget(self.lbl_filter_ativo)

        self.cmb_filter_ativo = QComboBox()
        self.cmb_filter_ativo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 100px;
                font-weight: bold;
                font-size: 9pt;
            }
            QComboBox::drop-down {
                border: 0;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e2f;
                color: #e0e0e0;
                selection-background-color: #2d2d44;
                selection-color: #1abc9c;
                border: 1px solid #2d2d44;
            }
        """)
        self.cmb_filter_ativo.addItem("TODOS")
        self.cmb_filter_ativo.currentIndexChanged.connect(self._on_filter_ativo_changed)
        btn_layout.addWidget(self.cmb_filter_ativo)

        btn_layout.addStretch()

        self.lbl_rtd_indicator = QLabel(" RTD: --- ")
        self.lbl_rtd_indicator.setFixedHeight(24)
        self._update_rtd_indicator(False)
        btn_layout.addWidget(self.lbl_rtd_indicator)

        self.btn_engine = QPushButton()
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "engine_perf.png")
        self.btn_engine.setIcon(QIcon(icon_path))
        self.btn_engine.setIconSize(QSize(16, 16))
        self.btn_engine.setToolTip("Engine Health & Performance (CPU/Memória)")
        self.btn_engine.setFixedSize(28, 24)
        self.btn_engine.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2f;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 2px;
            }
            QPushButton:hover { background-color: #2d2d44; }
        """)
        self.btn_engine.clicked.connect(self._abrir_engine_dashboard)
        btn_layout.addWidget(self.btn_engine)

        self.btn_parametros = QPushButton("⚙")
        self.btn_parametros.setToolTip("Parametros Operacionais")
        self.btn_parametros.setFixedSize(28, 24)
        self.btn_parametros.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                padding: 0;
            }
            QPushButton:hover { background-color: #2d2d44; color: #1abc9c; }
        """)
        self.btn_parametros.clicked.connect(self._abrir_parametros)
        btn_layout.addWidget(self.btn_parametros)

        main_layout.addLayout(btn_layout)

    def _apply_hidden_columns(self):
        from PyQt5.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = settings.value("colunas_ocultas", None)
        
        if hidden_cols is None:
            hidden_cols = MonitorTableModel.HIDDEN_BY_DEFAULT
        elif isinstance(hidden_cols, str):
            hidden_cols = hidden_cols.split(",") if hidden_cols else []
        elif not isinstance(hidden_cols, list):
            hidden_cols = list(hidden_cols)

        for i, (_, col_key) in enumerate(MonitorTableModel.COLUMNS):
            self.table_view.setColumnHidden(i, col_key in hidden_cols)

    def _save_column_visibility(self):
        from PyQt5.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = []
        for i, (_, col_key) in enumerate(MonitorTableModel.COLUMNS):
            if self.table_view.isColumnHidden(i):
                hidden_cols.append(col_key)
        settings.setValue("colunas_ocultas", hidden_cols)

    def _show_column_menu(self, pos):
        menu = QMenu(self)
        header = self.table_view.horizontalHeader()
        col_actions = {}
        for i, (col_name, _) in enumerate(MonitorTableModel.COLUMNS):
            action = menu.addAction(col_name)
            action.setCheckable(True)
            action.setChecked(not self.table_view.isColumnHidden(i))
            col_actions[id(action)] = i
        chosen = menu.exec_(header.mapToGlobal(pos))
        if chosen is not None and id(chosen) in col_actions:
            col_idx = col_actions[id(chosen)]
            self.table_view.setColumnHidden(col_idx, not chosen.isChecked())
            self._save_column_visibility()

    def _setup_toolbar(self):
        toolbar = QToolBar("Arquivo")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Toolbar actions moved to UI; parameters now in footer

    def _setup_status_bar(self):
        self._status_left = QLabel("Pronto")
        self._status_left.setProperty("class", "")
        self._status_right = QLabel("")
        self._status_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusBar().addWidget(self._status_left, 1)
        self.statusBar().addPermanentWidget(self._status_right)
        self._update_cdi_display()

    def _update_rtd_indicator(self, connected: bool):
        if connected:
            self.lbl_rtd_indicator.setStyleSheet(
                "background-color: {}; color: #ffffff; border-radius: 4px; "
                "padding: 2px 10px; font-weight: bold; font-size: 9pt;".format(Palette.GREEN_DIM)
            )
            self.lbl_rtd_indicator.setText(" RTD: CONECTADO ")
        else:
            self.lbl_rtd_indicator.setStyleSheet(
                "background-color: {}; color: {}; border-radius: 4px; "
                "padding: 2px 10px; font-weight: bold; font-size: 9pt;".format(Palette.RED_DIM, Palette.RED)
            )
            self.lbl_rtd_indicator.setText(" RTD: OFF ")

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
        self._status_right.setStyleSheet(
            "background-color: #16213e; color: #00f2ff; border: 1px solid #2d2d44; "
            "border-radius: 4px; padding: 3px 10px; font-family: 'JetBrains Mono', Consolas, monospace; "
            "font-size: 8.5pt; font-weight: bold; margin-right: 8px;"
        )

    def _aplicar_tema_configurado(self):
        param_repo = ParametroRepository(self.db_path)
        param = param_repo.get_by_chave("tema_visual")
        theme_id = param.valor if param else 0.0
        self.setStyleSheet(get_theme_qss(theme_id))

    def _abrir_parametros(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Parametros Operacionais")
        dialog.setMinimumSize(560, 620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        widget = ParametrosWidget(self.db_path)
        layout.addWidget(widget)
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dialog.accept)
        layout.addWidget(btn_fechar)
        dialog.exec_()
        self._aplicar_tema_configurado()
        self._worker.recarregar_parametros()
        self._update_cdi_display()

    def _toggle_monitor(self, checked):
        if checked:
            self.btn_varrer.setText("⏸  Pausar Monitor")
            self.btn_varrer.setProperty("class", "monitor-active")
            self.btn_varrer.style().unpolish(self.btn_varrer)
            self.btn_varrer.style().polish(self.btn_varrer)
            self.btn_import.setEnabled(False)
            self._update_rtd_indicator(self._rtd_connected)
            if not self._worker.isRunning():
                self._worker.start()
            else:
                self._worker.retomar()
            self._status_left.setText("Monitor ativo")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
            self._update_cdi_display()
        else:
            self.btn_varrer.setText("▶  Iniciar Monitor")
            self.btn_varrer.setProperty("class", "success")
            self.btn_varrer.style().unpolish(self.btn_varrer)
            self.btn_varrer.style().polish(self.btn_varrer)
            self.btn_import.setEnabled(True)
            self._update_rtd_indicator(False)
            if self._worker.isRunning():
                self._worker.pausar()
            self._status_left.setText("Monitor pausado")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.ORANGE))

    def _on_tp_op_toggled(self, checked):
        self._worker.set_mostrar_tp_op(checked)

    def _on_rtd_status(self, connected: bool):
        self._rtd_connected = connected
        self._update_rtd_indicator(connected)
        if self._colar_dialog and self._colar_dialog.isVisible():
            self._colar_dialog.set_rtd_status(connected)

    def _on_oportunidades_atualizadas(self, resultados: list):
        self._resultados_brutos = resultados
        self._filtrar_e_atualizar_tabela()

    def _filtrar_e_atualizar_tabela(self):
        ativo_filtro = self.cmb_filter_ativo.currentText()
        if ativo_filtro == "TODOS":
            filtrados = self._resultados_brutos
        else:
            filtrados = [r for r in self._resultados_brutos if r.ativo == ativo_filtro]

        self.table_model.atualizar(filtrados)
        self._total_opps = len(filtrados)
        self._total_viaveis = sum(1 for r in filtrados if r.viavel)
        viaveis_color = Palette.GREEN if self._total_viaveis > 0 else Palette.TEXT_MUTED
        self.lbl_count.setText(
            '<span style="color:{}">{} oportunidades</span> | '
            '<span style="color:{}; font-weight:bold">{} viaveis</span>'.format(
                Palette.TEXT_SECONDARY, self._total_opps, viaveis_color, self._total_viaveis
            )
        )
        self.lbl_count.repaint()
        self._last_scan_time = datetime.now()
        self._update_rtd_indicator(self._rtd_connected)
        self._update_scan_status()

    def _on_filter_ativo_changed(self, index):
        self._filtrar_e_atualizar_tabela()

    def _refresh_ativos_filter(self):
        from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
        repo = InstrumentoRepository(self.db_path)
        try:
            all_inst = repo.get_all()
            ativos = sorted(list(set(i.ativo for i in all_inst if i.ativo)))
        except Exception:
            ativos = []

        current_selection = self.cmb_filter_ativo.currentText()

        self.cmb_filter_ativo.blockSignals(True)
        self.cmb_filter_ativo.clear()
        self.cmb_filter_ativo.addItem("TODOS")
        for ativo in ativos:
            if ativo:
                self.cmb_filter_ativo.addItem(ativo)

        idx = self.cmb_filter_ativo.findText(current_selection)
        if idx >= 0:
            self.cmb_filter_ativo.setCurrentIndex(idx)
        else:
            self.cmb_filter_ativo.setCurrentIndex(0)

        self.cmb_filter_ativo.blockSignals(False)

    def _on_status_message(self, msg: str):
        self._status_left.setText(msg)

    def _abrir_engine_dashboard(self):
        self._engine_dialog.exec_()

    def _on_engine_stats_updated(self, stats):
        self._engine_dialog.update_stats(stats)

    def _update_scan_status(self):
        if self._last_scan_time is None:
            return
        elapsed = (datetime.now() - self._last_scan_time).total_seconds()
        ts = self._last_scan_time.strftime("%H:%M:%S")
        self._status_left.setText(
            "Varredura: {} ({}s) | RTD: {}".format(
                ts, int(elapsed), "ON" if self._rtd_connected else "OFF"
            )
        )
        self._status_left.setStyleSheet("color: {};".format(Palette.TEXT_SECONDARY))

    def _abrir_importacao(self):
        dialog = ImportDialog(self.importar_uc, self)
        dialog.exec_()
        if dialog.result is not None:
            self._status_left.setText(
                "Importados {} instrumentos, {} ativos".format(
                    dialog.result.total_importados, len(dialog.result.ativos)
                )
            )
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
            self._worker.recarregar_instrumentos()
            self._refresh_ativos_filter()

    def _abrir_importflash(self):
        from PyQt5.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self,
            "ImportFlash",
            "Isso vai SUBSTITUIR toda a base de instrumentos "
            "pelos dados atuais do opcoes.net.br.\n\n"
            "O processo leva ~5 minutos.\n"
            "Continuar?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        from PyQt5.QtCore import QProcess
        script_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "validar_opcoes"
        self._importflash_process = QProcess(self)
        self._importflash_process.setWorkingDirectory(str(script_dir))
        script = str(script_dir / "importflash.py")

        self._importflash_process.readyReadStandardOutput.connect(
            lambda: self._on_importflash_output(
                self._importflash_process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            )
        )
        self._importflash_process.readyReadStandardError.connect(
            lambda: self._on_importflash_output(
                self._importflash_process.readAllStandardError().data().decode("utf-8", errors="replace"),
                is_error=True,
            )
        )
        self._importflash_process.finished.connect(self._on_importflash_finished)

        self.btn_importflash.setEnabled(False)
        self.btn_importflash.setText("⏳  ImportFlash...")
        self._status_left.setText("ImportFlash: varrendo opcoes.net.br...")
        self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.YELLOW))

        self._importflash_process.start(
            sys.executable, [script, "--excluir", "IBOV11", "--delay", "1.0", "--incluir", "VALE3"]
        )

    def _on_importflash_output(self, text: str, is_error=False):
        print(text, end="", flush=True)

    def _on_importflash_finished(self, exit_code, exit_status):
        self.btn_importflash.setEnabled(True)
        self.btn_importflash.setText("⚡  ImportFlash")
        if exit_code == 0:
            self._worker.recarregar_instrumentos()
            self._refresh_ativos_filter()
            self._status_left.setText("ImportFlash: concluido com sucesso!")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
        else:
            self._status_left.setText(f"ImportFlash: erro (codigo {exit_code})")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.RED))

    def _abrir_historico(self):
        from src.ui.desktop.historico_dialog import HistoricoDialog
        dialog = HistoricoDialog(self.db_path, self)
        dialog.exec_()

    def _abrir_dividendos(self):
        from src.ui.desktop.dividendos_dialog import DividendosDialog
        dialog = DividendosDialog(self.db_path, self)
        dialog.exec_()

    def _salvar_selecao_colar(self, ativos: list):
        self._colar_selecionados = ativos

    def _on_colares_atualizados(self, resultados: list):
        self._ultimos_colares = resultados
        n_viaveis = sum(1 for r in resultados if r.viavel)
        if n_viaveis > 0:
            self._status_colar.setText(f"🛡 {n_viaveis} colar{'es' if n_viaveis > 1 else ''}")
            self._status_colar.setStyleSheet(
                f"color: {Palette.GREEN}; font-weight: bold; padding: 0 8px;"
            )
        else:
            self._status_colar.setText("")
        if self._colar_dialog and self._colar_dialog.isVisible():
            self._colar_dialog.atualizar_resultados(resultados)
            self._colar_dialog.set_rtd_status(self._rtd_connected)

    def _abrir_colar(self):
        if self._colar_dialog and self._colar_dialog.isVisible():
            self._colar_dialog.raise_()
            return
        self._colar_dialog = ColarDialog(self, self.db_path)
        self._colar_dialog.iniciar_scan_signal.connect(self._worker.iniciar_auto_colar)
        self._colar_dialog.parar_scan_signal.connect(self._worker.parar_auto_colar)
        self._colar_dialog.selecao_alterada.connect(self._salvar_selecao_colar)
        if hasattr(self, "_colar_selecionados") and self._colar_selecionados:
            self._colar_dialog.restaurar_selecao(self._colar_selecionados)
        if getattr(self, "_colar_auto_active", False):
            self._colar_dialog.sync_auto_active()
        self._colar_dialog.atualizar_resultados(self._ultimos_colares)
        self._colar_dialog.set_rtd_status(self._rtd_connected)
        self._colar_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._colar_dialog.destroyed.connect(lambda: setattr(self, "_colar_dialog", None))
        self._colar_dialog.show()

    def _abrir_colar_calendario(self):
        if self._colar_cal_dialog and self._colar_cal_dialog.isVisible():
            self._colar_cal_dialog.raise_()
            return
        self._colar_cal_dialog = ColarCalendarioDialog(self, self.db_path)
        self._colar_cal_dialog.iniciar_scan_signal.connect(self._worker.iniciar_auto_colar_cal)
        self._colar_cal_dialog.parar_scan_signal.connect(self._worker.parar_auto_colar_cal)
        self._colar_cal_dialog.selecao_alterada.connect(self._salvar_selecao_colar_cal)
        if hasattr(self, "_colar_cal_selecionados") and self._colar_cal_selecionados:
            self._colar_cal_dialog.restaurar_selecao(self._colar_cal_selecionados)
        if getattr(self, "_colar_cal_auto_active", False):
            self._colar_cal_dialog.sync_auto_active()
        self._colar_cal_dialog.atualizar_resultados(self._ultimos_colares_cal)
        self._colar_cal_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._colar_cal_dialog.destroyed.connect(lambda: setattr(self, "_colar_cal_dialog", None))
        self._colar_cal_dialog.show()

    def _salvar_selecao_colar_cal(self, ativos: list):
        self._colar_cal_selecionados = ativos

    def _on_colares_calendario_atualizados(self, resultados: list):
        self._ultimos_colares_cal = resultados
        n_viaveis = sum(1 for r in resultados if r.viavel)
        if n_viaveis > 0:
            self._status_colar_cal.setText(f"📅 {n_viaveis}")
            self._status_colar_cal.setStyleSheet(
                f"color: {Palette.YELLOW}; font-weight: bold; padding: 0 8px;"
            )
        else:
            self._status_colar_cal.setText("")
        if self._colar_cal_dialog and self._colar_cal_dialog.isVisible():
            self._colar_cal_dialog.atualizar_resultados(resultados)

    def _on_row_double_clicked(self, index):
        opp = self.table_model.get_oportunidade(index.row())
        if opp is None:
            return
        dialog = ExportDialog(opp, self.exportar_uc, self, self.db_path)
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
