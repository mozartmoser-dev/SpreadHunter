import sys
import winsound
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QToolBar, QLabel, QDialog, QMessageBox,
    QHeaderView, QTableView, QAbstractItemView, QFrame, QMenu,
    QCheckBox, QComboBox, QStackedWidget, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QTimer, QSize, QProcess, QPropertyAnimation, QEasingCurve, QThread, Signal
from PySide6.QtGui import QFont, QColor, QBrush, QIcon, QPixmap, QPainter, QAction, QShortcut, QKeySequence


from src.infrastructure.persistence.database import get_db_path
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.ui.desktop.theme import DARK_THEME_QSS, Palette, get_theme_qss
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.ui.desktop.monitor_worker import MonitorWorker
from src.ui.desktop.export_dialog import ExportDialog
from src.ui.desktop.parametros_widget import ParametrosWidget
from src.ui.desktop.engine_dashboard import EngineDashboard
from src.ui.desktop.colar_dialog import ColarDialog
from src.ui.desktop.colar_calendario_dialog import ColarCalendarioDialog
from src.ui.desktop.box_dialog import BoxDialog
from src.ui.desktop.mpp_dialog import MppDialog
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas


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
        self._ultimos_boxes = []
        self._ultimos_mpp = []
        self._ultimos_mre = []

        self.exportar_uc = ExportarOperacaoUseCase(self.db_path)

        self._rtd_connected = False
        self._worker = MonitorWorker(self.db_path, None)
        self._worker.oportunidades_atualizadas.connect(self._on_oportunidades_atualizadas)
        self._worker.status_message.connect(self._on_status_message)
        self._worker.rtd_status.connect(self._on_rtd_status)
        self._worker.engine_stats_updated.connect(self._on_engine_stats_updated)
        self._worker.colares_atualizados.connect(self._on_colares_atualizados)

        self._worker.colares_calendario_atualizados.connect(self._on_colares_calendario_atualizados)
        self._worker.boxes_atualizados.connect(self._on_boxes_atualizados)
        self._worker.mpp_atualizados.connect(self._on_mpp_atualizados)
        self._worker.mpp_status_changed.connect(self._on_mpp_status_changed)
        self._worker.mre_atualizados.connect(self._on_mre_atualizados)

        self._engine_dialog = EngineDashboard(self)
        self._colar_dialog = None
        self._colar_cal_dialog = None
        self._box_dialog = None
        self._mpp_dialog = None
        self._som_ativado = False

        self._aplicar_tema_configurado()

        self._setup_ui()
        self._setup_status_bar()

        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._abrir_pipeline)

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._update_scan_status)
        self._scan_timer.start(1000)

    def _setup_ui(self):
        self.setWindowTitle("SpreadHunter — Monitor de Oportunidades")
        self.setMinimumSize(1200, 700)
        self.resize(1280, 720)

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
        self.table_view.horizontalHeader().setSectionsMovable(True)
        self.table_view.horizontalHeader().setDragEnabled(True)
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self._show_column_menu)
        self.table_view.horizontalHeader().sectionMoved.connect(lambda: salvar_ordem_colunas(self.table_view.horizontalHeader(), "main_table_order"))
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().hide()
        self.table_view.setShowGrid(True)
        self._apply_hidden_columns()
        restaurar_ordem_colunas(self.table_view.horizontalHeader(), "main_table_order")

        from src.ui.desktop.badge_delegate import BadgeDelegate
        delegate = BadgeDelegate(self.table_view)
        for idx, (col_name, col_key) in enumerate(MonitorTableModel.COLUMNS):
            if col_key in ("label_tipo", "liq_indicator"):
                self.table_view.setItemDelegateForColumn(idx, delegate)

        font = QFont("Consolas", 9)
        self.table_view.setFont(font)

        temas_dir = Path(__file__).parent.parent.parent.parent / "temas"
        self._splash_inicial = QLabel()
        pix_abertura = QPixmap(str(temas_dir / "shtemaabertura.jpeg"))
        if not pix_abertura.isNull():
            self._splash_inicial.setPixmap(pix_abertura.scaled(1200, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._splash_inicial.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._splash_inicial.setStyleSheet("background-color: #0d0d0d;")
        else:
            self._splash_inicial.setText("SPREADHUNTER")
            self._splash_inicial.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._splash_inicial.setStyleSheet("color: #4fc3f7; font-size: 36pt; font-weight: bold; background-color: #0d0d0d;")

        self._splash_transicao = QLabel()
        pix_trans = QPixmap(str(temas_dir / "shtemainicializando.jpeg"))
        if not pix_trans.isNull():
            self._splash_transicao.setPixmap(pix_trans.scaled(1200, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._splash_transicao.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._splash_transicao.setStyleSheet("background-color: #0d0d0d;")
        else:
            self._splash_transicao.setText("INICIALIZANDO...")
            self._splash_transicao.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._splash_transicao.setStyleSheet("color: #1abc9c; font-size: 36pt; font-weight: bold; background-color: #0d0d0d;")

        self._transicao_opacity = QGraphicsOpacityEffect(self._splash_transicao)
        self._transicao_opacity.setOpacity(1.0)
        self._splash_transicao.setGraphicsEffect(self._transicao_opacity)

        self._fade_anim = QPropertyAnimation(self._transicao_opacity, b"opacity")
        self._fade_anim.setDuration(800)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)

        self._disclaimer = QLabel()
        pix_disc = QPixmap(str(temas_dir / "Disclaimer.jpeg"))
        if not pix_disc.isNull():
            self._disclaimer.setPixmap(pix_disc.scaled(1200, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._disclaimer.setStyleSheet("background-color: #0d0d0d;")
        else:
            self._disclaimer.setWordWrap(True)
            self._disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._disclaimer.setText(
                "<h3 style='color:#e0e0e0;'>Aviso de Risco</h3>"
                "<p style='color:#999; font-size:10pt; line-height:1.6;'>"
                "Operações com opções envolvem riscos significativos.<br>"
                "Este sistema é uma ferramenta de análise, não uma recomendação.<br>"
                "Você é o único responsável por suas decisões de investimento.<br><br>"
                "<span style='color:#4fc3f7;'>Clique em qualquer lugar para continuar.</span>"
                "</p>"
            )
            self._disclaimer.setStyleSheet(
                "background-color: rgba(13, 13, 13, 220); border: none; padding: 40px;"
            )
        self._disclaimer.mousePressEvent = lambda _: self._fechar_disclaimer()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._splash_inicial)
        self._stack.addWidget(self._splash_transicao)
        self._stack.addWidget(self.table_view)
        self._stack.addWidget(self._disclaimer)
        self._stack.setCurrentIndex(0)
        main_layout.addWidget(self._stack, stretch=1)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #2d2d44; max-height: 1px;")
        main_layout.addWidget(separator)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_calc = QPushButton("🧮  B&S")
        self.btn_calc.setProperty("class", "primary")
        self.btn_calc.clicked.connect(self._abrir_calculadora)
        btn_layout.addWidget(self.btn_calc)

        self.btn_importflash = QPushButton("⚡  Importar")
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

        self.btn_feriados = QPushButton("🗓  Feriados")
        self.btn_feriados.clicked.connect(self._abrir_feriados)
        btn_layout.addWidget(self.btn_feriados)

        self.btn_colar = QPushButton("🛡  Collar")
        self.btn_colar.clicked.connect(self._abrir_colar)
        btn_layout.addWidget(self.btn_colar)

        self.btn_colar_cal = QPushButton("📅  Collar")
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

        self.btn_box = QPushButton("📦  Box 4P")
        self.btn_box.clicked.connect(self._abrir_box)
        self.btn_box.setStyleSheet(f"""
            QPushButton {{
                background-color: #3d0e0e; color: {Palette.TEXT_PRIMARY};
                border: 1px solid #e74c3c; border-radius: 4px;
                padding: 6px 12px; font-size: 9pt; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #5d1e1e; }}
        """)
        btn_layout.addWidget(self.btn_box)

        self.btn_mpp = QPushButton("🎯  MPP")
        self.btn_mpp.clicked.connect(self._abrir_mpp)
        self.btn_mpp.setStyleSheet(f"""
            QPushButton {{
                background-color: #0e2d1e; color: {Palette.TEXT_PRIMARY};
                border: 1px solid #22c55e; border-radius: 4px;
                padding: 6px 12px; font-size: 9pt; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1a3d2e; }}
        """)
        btn_layout.addWidget(self.btn_mpp)

        self.btn_varrer = QPushButton("▶  Ligar")
        self.btn_varrer.setCheckable(True)
        self.btn_varrer.setChecked(False)
        self.btn_varrer.setProperty("class", "success")
        self.btn_varrer.clicked.connect(self._toggle_monitor)
        btn_layout.addWidget(self.btn_varrer)

        btn_layout.addSpacing(16)

        self.chk_tp_op = QCheckBox("Exibir Todas")
        self.chk_tp_op.setChecked(False)
        self.chk_tp_op.setStyleSheet(
            "QCheckBox {{ color: {}; spacing: 4px; font-size: 9pt; }}"
            "QCheckBox::indicator {{"
            "  width: 14px; height: 14px;"
            "  border: 1px solid {}; border-radius: 2px;"
            "  background-color: transparent;"
            "}}"
            "QCheckBox::indicator:checked {{"
            "  background-color: {};"
            "  border: 1px solid {};"
            "}}"
            "QCheckBox:hover {{ color: {}; }}"
            "QCheckBox::indicator:hover {{"
            "  border: 1px solid {};"
            "}}".format(
                Palette.TEXT_MUTED,
                Palette.BORDER, Palette.ACCENT_BLUE_BRIGHT, Palette.ACCENT_BLUE_BRIGHT,
                Palette.TEXT_PRIMARY,
                Palette.TEXT_PRIMARY,
            )
        )
        self.chk_tp_op.toggled.connect(self._on_tp_op_toggled)
        btn_layout.addWidget(self.chk_tp_op)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(
            "color: {}; font-size: 9pt; font-weight: bold; padding: 0 6px;".format(Palette.TEXT_SECONDARY)
        )

        self._status_colar = QLabel("")
        self._status_colar.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; padding: 0 6px;".format(Palette.GREEN))
        self._status_colar_cal = QLabel("")
        self._status_colar_cal.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; padding: 0 6px;".format(Palette.YELLOW))
        self._status_box = QLabel("")
        self._status_box.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; padding: 0 6px;".format(Palette.RED))

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
        self.btn_bell.toggled.connect(self._toggle_som_global)
        btn_layout.addWidget(self.btn_bell)

        btn_layout.addSpacing(16)
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

        self.btn_regras = QPushButton("📋")
        self.btn_regras.setToolTip("Regras e Filtros (Monitor BOX/SBTH)")
        self.btn_regras.setFixedSize(26, 24)
        self.btn_regras.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8a8ae0;
                border: 1px solid #8a8ae066; border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #8a8ae022; color: #b0b0ff; }
        """)
        self.btn_regras.setVisible(False)
        self.btn_regras.clicked.connect(self._abrir_regras_monitor)
        btn_layout.addWidget(self.btn_regras)

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
        from PySide6.QtCore import QSettings
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
        from PySide6.QtCore import QSettings
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

    def _setup_status_bar(self):
        self._status_left = QLabel("Pronto")
        self._status_left.setProperty("class", "")
        self.statusBar().addWidget(self._status_left, 1)

        self.lbl_count.setVisible(True)
        self._status_colar.setVisible(True)
        self._status_colar_cal.setVisible(True)
        self._status_box.setVisible(True)

        for w in (self.lbl_count, self._status_colar, self._status_colar_cal, self._status_box):
            self.statusBar().addPermanentWidget(w)

        self._status_right = QPushButton("")
        self._status_right.setFlat(True)
        self._status_right.setCursor(Qt.PointingHandCursor)
        self._status_right.clicked.connect(self._mostrar_vencimentos)
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
        cdi_dia_252 = (1 + taxa_cdi) ** (1 / 252) - 1 if taxa_cdi > 0 else 0.0
        cdi_dia_252_pct = cdi_dia_252 * 100
        cdi_dia_365 = (1 + taxa_cdi) ** (1 / 365) - 1 if taxa_cdi > 0 else 0.0
        cdi_dia_365_pct = cdi_dia_365 * 100
        self._status_right.setText(
            "📅 CDI {:.2f}%a | {:.4f}%m\n"
            "   DU {:.4f}%d | DC {:.4f}%d".format(
                cdi_anual_pct, cdi_mes_pct,
                cdi_dia_252_pct, cdi_dia_365_pct,
            )
        )
        self._status_right.setStyleSheet(
            "QPushButton { background-color: #16213e; color: #00f2ff; border: 1px solid #2d2d44; "
            "border-radius: 4px; padding: 4px 10px; font-family: 'JetBrains Mono', Consolas, monospace; "
            "font-size: 8pt; font-weight: bold; margin-right: 8px; text-align: right; }"
            "QPushButton:hover { border: 1px solid #00f2ff; background-color: #1a2a4e; }"
        )

    def _mostrar_vencimentos(self):
        from datetime import date
        from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
        from src.domain.services.calendario_b3 import dc_to_du
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout

        repo = InstrumentoRepository(self.db_path)
        vencimentos = repo.get_proximos_vencimentos(limite=30)
        if not vencimentos:
            return

        param_repo = ParametroRepository(self.db_path)
        param = param_repo.get_by_chave("taxa_cdi")
        taxa_cdi = param.valor if param else 0.1450
        hoje = date.today()

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle("Próximos Vencimentos")
        dialog.setMinimumSize(420, 350)
        dialog.setStyleSheet("background-color: #0d0d1a; color: #e0e0e0;")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Vencimento", "DTE", "CDI D.U.", "CDI D.C."])
        table.setRowCount(len(vencimentos))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().hide()

        header_style = (
            "QHeaderView::section { background-color: #16213e; color: #00f2ff; "
            "font-weight: bold; font-size: 9pt; padding: 4px; border: 1px solid #2d2d44; }"
        )
        table.horizontalHeader().setStyleSheet(header_style)
        table.setStyleSheet(
            "QTableWidget { background-color: #0d0d1a; color: #e0e0e0; "
            "font-size: 9pt; font-family: Consolas; border: 1px solid #2d2d44; }"
            "QTableWidget::item { padding: 2px 8px; }"
        )

        fmt_style = "color: #00f2ff; font-weight: bold;"

        for i, venc in enumerate(vencimentos):
            item_venc = QTableWidgetItem(venc.strftime("%d/%m/%Y"))
            item_venc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 0, item_venc)

            dc = (venc - hoje).days
            du = dc_to_du(hoje, venc)
            cdi_du = ((1 + taxa_cdi) ** (du / 252) - 1) * 100 if du > 0 else 0.0
            cdi_dc = ((1 + taxa_cdi) ** (dc / 365) - 1) * 100 if dc > 0 else 0.0

            item_dte = QTableWidgetItem(f"{dc}d")
            item_dte.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, item_dte)

            item_cdi_du = QTableWidgetItem(f"{cdi_du:.4f}%")
            item_cdi_du.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cdi_du.setForeground(QColor("#00f2ff"))
            table.setItem(i, 2, item_cdi_du)

            item_cdi_dc = QTableWidgetItem(f"{cdi_dc:.4f}%")
            item_cdi_dc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cdi_dc.setForeground(QColor("#00f2ff"))
            table.setItem(i, 3, item_cdi_dc)

        table.resizeColumnsToContents()
        layout.addWidget(table)
        dialog.exec_()

    def _aplicar_tema_configurado(self):
        param_repo = ParametroRepository(self.db_path)
        param = param_repo.get_by_chave("tema_visual")
        theme_id = param.valor if param else 0.0
        self.setStyleSheet(get_theme_qss(theme_id))

    def _abrir_regras_monitor(self):
        from src.ui.desktop.regras_dialog import RegrasDialog
        dlg = RegrasDialog("BOX", self.db_path, self)
        dlg.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self.btn_regras.setVisible(not self.btn_regras.isVisible())
        else:
            super().keyPressEvent(event)

    def _abrir_pipeline(self):
        from src.ui.desktop.pipeline_dialog import PipelineDialog
        tracker = getattr(self._worker._monitor_uc, '_ultimo_pipeline', None) if hasattr(self, '_worker') else None
        dlg = PipelineDialog(tracker, self)
        dlg.exec_()

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

    def _on_fade_finished(self):
        self._transicao_opacity.setOpacity(1.0)
        if self._stack.currentIndex() == 1:
            self._stack.setCurrentIndex(3)

    def _fechar_disclaimer(self):
        self._stack.setCurrentIndex(2)

    def _toggle_monitor(self, checked):
        if checked:
            self._stack.setCurrentIndex(1)
            QTimer.singleShot(1500, self._fade_anim.start)
            self.btn_varrer.setText("⏸  Desligar")
            self.btn_varrer.setProperty("class", "monitor-active")
            self.btn_varrer.style().unpolish(self.btn_varrer)
            self.btn_varrer.style().polish(self.btn_varrer)
            self._update_rtd_indicator(self._rtd_connected)
            if not self._worker.isRunning():
                self._worker.start()
            else:
                self._worker.retomar()
            self._status_left.setText("Monitor ativo")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
            self._update_cdi_display()
        else:
            self._stack.setCurrentIndex(0)
            self._transicao_opacity.setOpacity(1.0)
            self.btn_varrer.setText("▶  Ligar")
            self.btn_varrer.setProperty("class", "success")
            self.btn_varrer.style().unpolish(self.btn_varrer)
            self.btn_varrer.style().polish(self.btn_varrer)
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
        self.table_model.atualizar(self._resultados_brutos)
        self._total_opps = len(self._resultados_brutos)
        self._total_viaveis = sum(1 for r in self._resultados_brutos if r.viavel)
        if self._total_opps > 0:
            cor = Palette.GREEN if self._total_viaveis > 0 else Palette.TEXT_MUTED
            self.lbl_count.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold; padding: 0 6px;")
            self.lbl_count.setText(f"{self._total_opps} opps | {self._total_viaveis} viav")
        else:
            self.lbl_count.setText("")
        self._last_scan_time = datetime.now()
        self._update_rtd_indicator(self._rtd_connected)
        self._update_scan_status()

        if self._som_ativado and self._total_viaveis > 0:
            self._tocar_beep()

    def _tocar_beep(self):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: winsound.Beep(1000, 200))
        QTimer.singleShot(200, lambda: winsound.Beep(1200, 150))

    def _toggle_som_global(self, ativo: bool):
        self._som_ativado = ativo
        self.btn_bell.setToolTip("Som: ligado" if ativo else "Som: desligado")

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

    def _abrir_calculadora(self):
        from src.ui.desktop.calculadora_dialog import CalculadoraDialog
        dialog = CalculadoraDialog(self)
        dialog.exec_()

    def _abrir_importflash(self):
        from src.ui.desktop.blacklist_import_dialog import BlacklistImportDialog
        dlg = BlacklistImportDialog(self.db_path, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        self.btn_importflash.setEnabled(False)
        self.btn_importflash.setText("⏳  Importar...")
        self._status_left.setText("ImportFlash: varrendo opcoes.net.br...")
        self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.YELLOW))

        class _ImportThread(QThread):
            finished = Signal(int)
            progress = Signal(str)

            def run(self):
                import io, contextlib

                class _LineCapture(io.StringIO):
                    def __init__(self, sig_target):
                        super().__init__()
                        self._buf = io.StringIO()
                        self._partial = ""
                        self._sig_target = sig_target

                    def write(self, s):
                        self._buf.write(s)
                        self._partial += s
                        while "\n" in self._partial:
                            idx = self._partial.index("\n")
                            line = self._partial[:idx]
                            self._partial = self._partial[idx + 1 :]
                            if line:
                                self._sig_target.emit(line)

                    def flush(self):
                        pass

                    def getvalue(self):
                        return self._buf.getvalue()

                captura = _LineCapture(self.progress)
                with contextlib.redirect_stdout(captura), contextlib.redirect_stderr(captura):
                    try:
                        from scripts.validar_opcoes.importflash import main
                        rc = main()
                    except Exception as e:
                        print(f"ERRO: {e}")
                        import traceback
                        traceback.print_exc()
                        rc = 1
                output = captura.getvalue()
                if output:
                    print(output, end="", flush=True)
                self.finished.emit(rc if rc is not None else 1)

        self._import_thread = _ImportThread()
        self._import_thread.finished.connect(self._on_importflash_finished)
        self._import_thread.progress.connect(
            lambda msg: self._status_left.setText(f"ImportFlash: {msg[:120]}")
        )
        self._import_thread.start()

    def _on_importflash_finished(self, exit_code: int):
        self.btn_importflash.setEnabled(True)
        self.btn_importflash.setText("⚡  Importar")
        if exit_code == 0:
            self._worker.recarregar_instrumentos()
            self._status_left.setText("ImportFlash: concluido com sucesso!")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
            QMessageBox.information(self, "Importação", "Importação concluída com sucesso!")
        else:
            self._status_left.setText(f"ImportFlash: erro (codigo {exit_code})")
            self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.RED))
            QMessageBox.critical(self, "Importação", f"Importação falhou (código {exit_code}).")

    def _abrir_historico(self):
        from src.ui.desktop.historico_dialog import HistoricoDialog
        dialog = HistoricoDialog(self.db_path, self)
        dialog.exec_()

    def _abrir_dividendos(self):
        from src.ui.desktop.dividendos_dialog import DividendosDialog
        dialog = DividendosDialog(self.db_path, self)
        dialog.exec_()

    def _abrir_feriados(self):
        from src.ui.desktop.feriados_dialog import FeriadosDialog
        from src.domain.services.calendario_b3 import carregar_do_banco
        dialog = FeriadosDialog(self.db_path, self)
        dialog.exec_()
        carregar_do_banco(self.db_path)

    def _salvar_selecao_colar(self, ativos: list):
        self._colar_selecionados = ativos

    def _on_colares_atualizados(self, resultados: list):
        self._ultimos_colares = resultados
        n_viaveis = sum(1 for r in resultados if r.viavel)
        n_total = len(resultados)
        agora = datetime.now().strftime("%H:%M:%S")
        self._status_colar.setText(f"🛡 {n_viaveis}")
        self._status_colar.setToolTip(
            f"Collar Protetivo\n"
            f"Viáveis: {n_viaveis} / {n_total}\n"
            f"Última: {agora}"
        )
        self._status_colar.setStyleSheet(
            f"color: {Palette.GREEN}; font-weight: bold; padding: 0 6px;"
        )
        if self._colar_dialog and self._colar_dialog.isVisible():
            self._colar_dialog.atualizar_resultados(resultados)
            self._colar_dialog.set_rtd_status(self._rtd_connected)

    def _abrir_colar(self):
        if self._colar_dialog and self._colar_dialog.isVisible():
            self._colar_dialog.raise_()
            return
        self._colar_dialog = ColarDialog(self, self.db_path)
        self._colar_dialog.iniciar_scan_signal.connect(self._worker.iniciar_auto_colar)
        self._colar_dialog.parar_scan_signal.connect(self._on_parar_colar)
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

    def _on_parar_colar(self):
        self._worker.parar_auto_colar()
        self._status_colar.setText("🛡 0")

    def _abrir_colar_calendario(self):
        if self._colar_cal_dialog and self._colar_cal_dialog.isVisible():
            self._colar_cal_dialog.raise_()
            return
        self._colar_cal_dialog = ColarCalendarioDialog(self, self.db_path)
        self._colar_cal_dialog.iniciar_scan_signal.connect(self._worker.iniciar_auto_colar_cal)
        self._colar_cal_dialog.parar_scan_signal.connect(self._on_parar_colar_cal)
        self._colar_cal_dialog.selecao_alterada.connect(self._salvar_selecao_colar_cal)
        if hasattr(self, "_colar_cal_selecionados") and self._colar_cal_selecionados:
            self._colar_cal_dialog.restaurar_selecao(self._colar_cal_selecionados)
        if getattr(self, "_colar_cal_auto_active", False):
            self._colar_cal_dialog.sync_auto_active()
        self._colar_cal_dialog.atualizar_resultados(self._ultimos_colares_cal)
        self._colar_cal_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._colar_cal_dialog.destroyed.connect(lambda: setattr(self, "_colar_cal_dialog", None))
        self._colar_cal_dialog.show()

    def _on_parar_colar_cal(self):
        self._worker.parar_auto_colar_cal()
        self._status_colar_cal.setText("📅 0")

    def _salvar_selecao_colar_cal(self, ativos: list):
        self._colar_cal_selecionados = ativos

    def _on_colares_calendario_atualizados(self, resultados: list):
        self._ultimos_colares_cal = resultados
        n_viaveis = sum(1 for r in resultados if r.viavel)
        n_total = len(resultados)
        agora = datetime.now().strftime("%H:%M:%S")
        self._status_colar_cal.setText(f"📅 {n_viaveis}")
        self._status_colar_cal.setToolTip(
            f"Collar Calendário\n"
            f"Viáveis: {n_viaveis} / {n_total}\n"
            f"Última: {agora}"
        )
        self._status_colar_cal.setStyleSheet(
            f"color: {Palette.YELLOW}; font-weight: bold; padding: 0 6px;"
        )
        if self._colar_cal_dialog and self._colar_cal_dialog.isVisible():
            self._colar_cal_dialog.atualizar_resultados(resultados)

    def _on_boxes_atualizados(self, resultados: list):
        self._ultimos_boxes = resultados
        n_viaveis = sum(1 for r in resultados if r.viavel)
        n_total = len(resultados)
        agora = datetime.now().strftime("%H:%M:%S")
        self._status_box.setText(f"📦 {n_viaveis}")
        self._status_box.setToolTip(
            f"Box 4 Pontas\n"
            f"Viáveis: {n_viaveis} / {n_total}\n"
            f"Última: {agora}"
        )
        self._status_box.setStyleSheet(
            f"color: {Palette.RED}; font-weight: bold; padding: 0 6px;"
        )
        if self._box_dialog and self._box_dialog.isVisible():
            self._box_dialog.atualizar_resultados(resultados)

    def _abrir_box(self):
        if self._box_dialog and self._box_dialog.isVisible():
            self._box_dialog.raise_()
            return
        self._box_dialog = BoxDialog(self, self.db_path)
        self._box_dialog.iniciar_scan_signal.connect(self._worker.iniciar_auto_box)
        self._box_dialog.parar_scan_signal.connect(self._on_parar_box)
        self._box_dialog.atualizar_resultados(self._ultimos_boxes)
        self._box_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._box_dialog.destroyed.connect(lambda: setattr(self, "_box_dialog", None))
        self._box_dialog.show()

    def _on_parar_box(self):
        self._worker.parar_auto_box()
        self._status_box.setText("📦 0")

    def _on_mpp_atualizados(self, resultados: list):
        self._ultimos_mpp = resultados
        if self._mpp_dialog and self._mpp_dialog.isVisible():
            self._mpp_dialog.atualizar(resultados, self._ultimos_mre)

    def _on_mpp_status_changed(self, enabled: bool):
        if self._mpp_dialog and self._mpp_dialog.isVisible():
            self._mpp_dialog.set_status_enabled(enabled)

    def _on_mre_atualizados(self, resultados: list):
        self._ultimos_mre = resultados
        if self._mpp_dialog and self._mpp_dialog.isVisible():
            self._mpp_dialog.atualizar(self._ultimos_mpp, resultados)

    def _abrir_mpp(self):
        if self._mpp_dialog and self._mpp_dialog.isVisible():
            self._mpp_dialog.raise_()
            return
        self._mpp_dialog = MppDialog(self, self.db_path)
        self._mpp_dialog.atualizar(self._ultimos_mpp, self._ultimos_mre)
        self._mpp_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        mpp_active = self._worker._mpp_habilitado and self._worker._mpp_carga_completa
        self._mpp_dialog.set_status_enabled(mpp_active)
        self._mpp_dialog.destroyed.connect(lambda: setattr(self, "_mpp_dialog", None))
        self._mpp_dialog.show()

    def _on_row_double_clicked(self, index):
        opp = self.table_model.get_oportunidade(index.row())
        if opp is None:
            return
        dialog = ExportDialog(opp, self.exportar_uc, self, self.db_path)
        dialog.exec_()

    def closeEvent(self, event):
        self._worker.parar()
        self._worker.finished.connect(self._worker.deleteLater)
        super().closeEvent(event)

    def start_auto_scan(self, interval_ms: int = 1500):
        self._worker.set_interval(interval_ms)
        self.btn_varrer.setChecked(True)
        self._toggle_monitor(True)

    def stop_auto_scan(self):
        self.btn_varrer.setChecked(False)
        self._toggle_monitor(False)
