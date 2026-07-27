import sys
from collections import Counter
from datetime import datetime
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QToolBar, QToolButton, QLabel, QDialog, QMessageBox,
    QHeaderView, QTableView, QAbstractItemView, QFrame, QMenu,
    QAbstractSpinBox, QCheckBox, QComboBox, QSpinBox, QStackedWidget, QGraphicsOpacityEffect,
    QSplitter,
)
from PySide6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, QThread, Signal, QUrl, QSortFilterProxyModel
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QFont, QColor, QBrush, QIcon, QPixmap, QPainter, QAction, QShortcut, QKeySequence, QMovie


from src.infrastructure.persistence.database import get_db_path
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.ui.desktop.theme import DARK_THEME_QSS, Palette, get_theme_qss
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.ui.desktop.vendidas_table_model import VendidasTableModel
from src.ui.desktop.venda_coberta_table_model import VendaCobertaTableModel
from src.ui.desktop.monitor_worker import MonitorWorker
from src.ui.desktop.export_dialog import ExportDialog
from src.ui.desktop.parametros_widget import ParametrosWidget
from src.ui.desktop.engine_dashboard import EngineDashboard
from src.ui.desktop.sensibilidade_mercado_widget import SensibilidadeMercadoWidget
from src.ui.desktop.colar_dialog import ColarDialog
from src.ui.desktop.colar_calendario_dialog import ColarCalendarioDialog
from src.ui.desktop.box_dialog import BoxDialog
from src.ui.desktop.mpp_dialog import MppDialog
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.ui.desktop.column_utils import (
    salvar_ordem_colunas,
    salvar_largura_colunas,
    limpar_e_restaurar_colunas,
)
from src.ui.desktop.mercado_topbar import MercadoTopBarWidget


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


class TopNSortProxy(QSortFilterProxyModel):
    """Proxy que mantém só as N melhores linhas por ativo (coluna 1).

    Agrupa linhas pelo valor da coluna ``_ativo_col`` (default 1 = "Ativo"),
    ordena cada grupo pela coluna de ordenação atual (ou ``_default_sort_col``
    se nenhuma), e mantém só as ``_top_n`` primeiras de cada grupo.
    ``_top_n = 0`` = desliga o filtro (mostra todos).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._top_n = 0
        self._top_n_accept_set: set[int] | None = None
        self._default_sort_col = 3
        self._ativo_col = 1

    def set_top_n(self, n: int):
        self._top_n = n
        self._top_n_accept_set = None
        self.invalidateFilter()

    def invalidate_top_n(self):
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
            sort_col = self._default_sort_col
        sort_order = self.sortOrder()

        rows_by_ativo: dict[str, list[int]] = {}
        for row in range(src.rowCount()):
            idx = src.index(row, self._ativo_col)
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
        if self._top_n > 0:
            if self._top_n_accept_set is None:
                self._recompute_top_n()
            if row not in self._top_n_accept_set:
                return False
        return True


class MainWindow(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.db_path = db_path or str(get_db_path())
        self._last_scan_time = None
        self._total_opps = 0
        self._total_viaveis = 0
        self._resultados_brutos = []
        self._resultados_vendidas = []
        self._resultados_coberta = []
        self._filtro_vencimento: str | None = None
        self._filtro_vencimento_vendidas: str | None = None
        self._filtro_vencimento_coberta: str | None = None
        self._foco_vendidas = False
        self._foco_coberta = False
        self._ultimos_colares = []
        self._ultimos_colares_cal = []
        self._ultimos_boxes = []
        self._ultimos_put_ratio = []
        self._ultimos_mpp = []
        self._ultimos_mre = []

        self.exportar_uc = ExportarOperacaoUseCase(self.db_path)

        self._rtd_connected = False
        self._worker = MonitorWorker(self.db_path, None)
        self._worker.oportunidades_atualizadas.connect(self._on_oportunidades_atualizadas)
        self._worker.oportunidades_vendidas_atualizadas.connect(self._on_oportunidades_vendidas_atualizadas)
        self._worker.oportunidades_coberta_atualizadas.connect(self._on_oportunidades_coberta_atualizadas)
        self._worker.status_message.connect(self._on_status_message)
        self._worker.rtd_status.connect(self._on_rtd_status)
        self._worker.engine_stats_updated.connect(self._on_engine_stats_updated)
        self._worker.colares_atualizados.connect(self._on_colares_atualizados)

        self._worker.colares_calendario_atualizados.connect(self._on_colares_calendario_atualizados)
        self._worker.boxes_atualizados.connect(self._on_boxes_atualizados)
        self._worker.put_ratio_atualizados.connect(self._on_put_ratio_atualizados)
        self._worker.mpp_atualizados.connect(self._on_mpp_atualizados)
        self._worker.mpp_status_changed.connect(self._on_mpp_status_changed)
        self._worker.mre_atualizados.connect(self._on_mre_atualizados)

        self._engine_dialog = EngineDashboard(self)
        self._colar_dialog = None
        self._colar_cal_dialog = None
        self._box_dialog = None
        self._put_ratio_dialog = None
        self._mpp_dialog = None
        self._som_ativado = False
        self._som_vendidas_ativado = False
        self._som_coberta_ativado = False

        self._aplicar_tema_configurado()

        self._setup_ui()
        self._setup_status_bar()

        self._sensibilidade_mercado: SensibilidadeMercadoWidget | None = None

        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._abrir_pipeline)

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._update_scan_status)
        self._scan_timer.start(1000)

    def _criar_dropup_paineis(self, _btn_base: str, _btn_hover: str) -> QToolButton:
        """Constrói o botão 🗂 Painéis que abre um dropup QMenu com os 7 dialogs."""

        class _BtnProxy:
            """Proxy leve preserva API setEnabled/setText dos antigos botões.

            Cada `self.btn_X` legado aponta para o QAction correspondente do
            menu, permitindo que o restante do código (que ainda usa
            `self.btn_taxa_aluguel.setEnabled(False)`) funcione sem refactor.
            """
            __slots__ = ("_action", "_default_text")

            def __init__(self, action: QAction, default_text: str):
                self._action = action
                self._default_text = default_text

            def setEnabled(self, enabled: bool):
                self._action.setEnabled(bool(enabled))

            def setText(self, text: str):
                # Quando vazio, restaura o label default do menu item
                self._action.setText(text or self._default_text)

            def setVisible(self, visible: bool):
                self._action.setVisible(bool(visible))

            def isEnabled(self) -> bool:
                return self._action.isEnabled()

        # Cores dos itens (mesmas usadas nos botões antigos)
        cor_grade = "#3a8fd4"
        cor_hist = "#9b59b6"
        cor_prov = "#27ae60"
        cor_res = "#e67e22"
        cor_fer = "#5a5a7a"
        cor_tx = "#f1c40f"
        cor_atu = "#27ae60"

        # --- QMenu com 7 ações ---
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px 6px 12px;
                border-radius: 4px;
                font-size: 9pt;
            }
            QMenu::item:selected { background-color: #2d4a7a; color: #ffffff; }
            QMenu::item:disabled { color: #5a5a6e; }
        """)

        def add_item(text: str, color_hex: str, slot) -> QAction:
            act = QAction(text, menu)
            act.triggered.connect(slot)
            # coloração do label via setData (apenas visual)
            from PySide6.QtGui import QColor as _QC
            act.setData(_QC(color_hex))
            # aplica cor via stylesheet por item (com QSS fragment em actionData)
            menu.addAction(act)
            return act

        self.action_btn_importflash = add_item(
            "\U0001f4ca  Grade de Opções", cor_grade, self._abrir_importflash,
        )
        self.action_btn_historico = add_item(
            "\U0001f4c8  Histórico Operações", cor_hist, self._abrir_historico,
        )
        self.action_btn_dividendos = add_item(
            "\U0001f4b0  Proventos", cor_prov, self._abrir_dividendos,
        )
        self.action_btn_resultados = add_item(
            "\U0001f4ca  Agenda de Balanços", cor_res, self._abrir_resultados,
        )
        self.action_btn_feriados = add_item(
            "\U0001f5d3  Feriados", cor_fer, self._abrir_feriados,
        )
        self.action_btn_estudos_cal = add_item(
            "\U0001f4ca  Estudos Calendário", "#00bcd4", self._abrir_estudos_calendario,
        )
        self.action_btn_taxa_aluguel = add_item(
            "\U0001f3e6  Taxa Aluguel", cor_tx, self._abrir_coletar_taxa_aluguel,
        )
        self.action_btn_atualizar_tudo = add_item(
            "\U0001f504  Atualizar Tudo", cor_atu, self._atualizar_tudo,
        )

        # Cores individuais por item via stylesheet dinâmico no paintEvent
        # — fallback: usa action.toolTip para documentar
        for act, cor in (
            (self.action_btn_importflash, cor_grade),
            (self.action_btn_historico, cor_hist),
            (self.action_btn_dividendos, cor_prov),
            (self.action_btn_resultados, cor_res),
            (self.action_btn_feriados, cor_fer),
            (self.action_btn_estudos_cal, "#00bcd4"),
            (self.action_btn_taxa_aluguel, cor_tx),
            (self.action_btn_atualizar_tudo, cor_atu),
        ):
            act.setToolTip(f"<span style='color:{cor};'>{act.text()}</span>")

        # --- QToolButton que hospeda o menu ---
        btn = QToolButton(self)
        btn.setText("\U0001fa9f  Painéis")
        btn.setToolTip(
            "Painéis: Grade de Opções · Histórico · Proventos · "
            "Resultados · Feriados · Estudos Calendário · Taxa Aluguel · Atualizar tudo"
        )
        btn.setPopupMode(QToolButton.InstantPopup)
        btn.setMenu(menu)
        btn.setAutoRaise(False)
        btn.setCursor(Qt.PointingHandCursor)
        # Estilo coerente com btn_calc: azul, hover azul mais claro
        btn.setStyleSheet(
            _btn_base
            + "QToolButton {{ color: #9b59b6; border-color: rgba(155,89,182,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QToolButton:hover {{ background-color: #2d1f3d; border-color: #9b59b6; }}"
            + "QToolButton:menu-indicator { image: none; subcontrol-position: right center; width: 12px; }"
        )

        # Dropup: ao mostrar, reposiciona menu acima do botão
        def _popup_acima(menu_obj: QMenu, btn_widget: QToolButton):
            from PySide6.QtCore import QPoint
            top_left = btn_widget.mapToGlobal(QPoint(0, 0))
            size = menu_obj.sizeHint()
            # posiciona com x = canto esquerdo do botão, y = topo do botão - altura menu
            x = top_left.x()
            y = top_left.y() - size.height()
            menu_obj.move(x, y)
            menu_obj.exec_()

        # Override: clicar no botão abre o menu manualmente para cima
        def _show_dropup():
            size = menu.sizeHint()
            from PySide6.QtCore import QPoint
            top_left = btn.mapToGlobal(QPoint(0, 0))
            x = top_left.x()
            y = top_left.y() - size.height()
            menu.move(x, y)
            menu.exec_()

        btn.clicked.connect(_show_dropup)
        # Conserva referência para evitar GC
        self._paineis_menu = menu
        self._paineis_btn = btn

        # Proxies para preservar API dos antigos botões no código restante
        self.btn_importflash = _BtnProxy(self.action_btn_importflash, "📊 Grade Opções")
        self.btn_historico = _BtnProxy(self.action_btn_historico, "📈 Histórico Operações")
        self.btn_dividendos = _BtnProxy(self.action_btn_dividendos, "💰 Prov.")
        self.btn_resultados = _BtnProxy(self.action_btn_resultados, "📊 Agenda de Balanços")
        self.btn_feriados = _BtnProxy(self.action_btn_feriados, "🗓 Fer.")
        self.btn_estudos_cal = _BtnProxy(self.action_btn_estudos_cal, "📊 Estudos Cal.")
        self.btn_taxa_aluguel = _BtnProxy(self.action_btn_taxa_aluguel, "🏦 Tx Alug.")
        self.btn_atualizar_tudo = _BtnProxy(self.action_btn_atualizar_tudo, "🔄 Atualizar")

        return btn

    def _setup_ui(self):
        self.setWindowTitle("SpreadHunter — Monitor de Oportunidades")
        self.setMinimumSize(1200, 700)
        self.resize(1280, 720)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(8)

        self.top_bar = MercadoTopBarWidget(db_path=self.db_path)
        main_layout.addWidget(self.top_bar)

        self.table_model = MonitorTableModel()
        self._main_proxy = TopNSortProxy()
        self._main_proxy.setSourceModel(self.table_model)
        self.table_view = QTableView()
        self.table_view.setModel(self._main_proxy)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.horizontalHeader().setSectionsMovable(True)
        self.table_view.horizontalHeader().setDragEnabled(True)
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self._show_column_menu)
        self.table_view.horizontalHeader().sectionMoved.connect(lambda: salvar_ordem_colunas(self.table_view.horizontalHeader(), "main_table_order"))
        self.table_view.horizontalHeader().sectionResized.connect(lambda: QTimer.singleShot(0, lambda: salvar_largura_colunas(self.table_view.horizontalHeader(), "main_table_width")))
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().hide()
        self.table_view.setShowGrid(True)
        self._apply_hidden_columns()
        limpar_e_restaurar_colunas(self.table_view.horizontalHeader(), "main_table_order", "main_table_width")
        self.table_view.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #1e1e1e; color: #4caf50; "
            "font-weight: bold; font-size: 9pt; padding: 4px 8px; border: 1px solid #333; }"
        )

        from src.ui.desktop.badge_delegate import BadgeDelegate
        delegate = BadgeDelegate(self.table_view)
        for idx, (col_name, col_key) in enumerate(MonitorTableModel.COLUMNS):
            if col_key in ("label_tipo", "liq_indicator"):
                self.table_view.setItemDelegateForColumn(idx, delegate)

        font = QFont("Consolas", 9)
        self.table_view.setFont(font)

        # --- Vendidas table ---
        self.vendidas_model = VendidasTableModel()
        self._vend_proxy = TopNSortProxy()
        self._vend_proxy.setSourceModel(self.vendidas_model)
        self.vendidas_table_view = QTableView()
        self.vendidas_table_view.setModel(self._vend_proxy)
        self.vendidas_table_view.setAlternatingRowColors(True)
        self.vendidas_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.vendidas_table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.vendidas_table_view.setSortingEnabled(True)
        self.vendidas_table_view.setFont(font)
        self.vendidas_table_view.verticalHeader().setDefaultSectionSize(28)
        self.vendidas_table_view.verticalHeader().hide()
        self.vendidas_table_view.setShowGrid(True)
        h2 = self.vendidas_table_view.horizontalHeader()
        h2.setStretchLastSection(True)
        h2.setSectionResizeMode(QHeaderView.ResizeToContents)
        h2.setSectionsMovable(True)
        h2.setDragEnabled(True)
        h2.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(h2, "vendidas_table_order")))
        h2.sectionResized.connect(lambda: QTimer.singleShot(0, lambda: salvar_largura_colunas(h2, "vendidas_table_width")))
        h2.setStyleSheet(
            "QHeaderView::section { background-color: #1e1e1e; color: #e57373; "
            "font-weight: bold; font-size: 9pt; padding: 4px 8px; border: 1px solid #333; }"
        )
        h2.setContextMenuPolicy(Qt.CustomContextMenu)
        h2.customContextMenuRequested.connect(self._show_column_menu_vendidas)
        for i in range(self.vendidas_model.columnCount()):
            self.vendidas_table_view.setColumnHidden(i, VendidasTableModel.COLUMNS[i][1] in VendidasTableModel.HIDDEN_BY_DEFAULT)
        self._apply_hidden_columns_vendidas()
        limpar_e_restaurar_colunas(h2, "vendidas_table_order", "vendidas_table_width")
        header_v = self.vendidas_table_view.verticalHeader()
        header_v.setDefaultSectionSize(28)
        header_v.hide()
        self.vendidas_table_view.mousePressEvent = lambda e: (setattr(self, '_foco_vendidas', True), setattr(self, '_foco_coberta', False), QTableView.mousePressEvent(self.vendidas_table_view, e))[2]
        self.vendidas_table_view.doubleClicked.connect(self._on_vendidas_row_double_clicked)
        self.table_view.mousePressEvent = lambda e: (setattr(self, '_foco_vendidas', False), setattr(self, '_foco_coberta', False), QTableView.mousePressEvent(self.table_view, e))[2]

        # --- Coberta table ---
        self.coberta_model = VendaCobertaTableModel()
        self._taxa_proxy = TopNSortProxy()
        self._taxa_proxy.setSourceModel(self.coberta_model)
        self.coberta_table_view = QTableView()
        self.coberta_table_view.setModel(self._taxa_proxy)
        self.coberta_table_view.setAlternatingRowColors(True)
        self.coberta_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.coberta_table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.coberta_table_view.setSortingEnabled(True)
        self.coberta_table_view.setFont(font)
        self.coberta_table_view.verticalHeader().setDefaultSectionSize(28)
        self.coberta_table_view.verticalHeader().hide()
        self.coberta_table_view.setShowGrid(True)
        h3 = self.coberta_table_view.horizontalHeader()
        h3.setStretchLastSection(True)
        h3.setSectionResizeMode(QHeaderView.ResizeToContents)
        h3.setSectionsMovable(True)
        h3.setDragEnabled(True)
        h3.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(h3, "coberta_table_order")))
        h3.sectionResized.connect(lambda: QTimer.singleShot(0, lambda: salvar_largura_colunas(h3, "coberta_table_width")))
        h3.setStyleSheet(
            "QHeaderView::section { background-color: #1e1e1e; color: #42a5f5; "
            "font-weight: bold; font-size: 9pt; padding: 4px 8px; border: 1px solid #333; }"
        )
        h3.setContextMenuPolicy(Qt.CustomContextMenu)
        h3.customContextMenuRequested.connect(self._show_column_menu_coberta)
        for i in range(self.coberta_model.columnCount()):
            self.coberta_table_view.setColumnHidden(i, VendaCobertaTableModel.COLUMNS[i][1] in VendaCobertaTableModel.HIDDEN_BY_DEFAULT)
        self._apply_hidden_columns_coberta()
        limpar_e_restaurar_colunas(h3, "coberta_table_order", "coberta_table_width")
        header_co = self.coberta_table_view.verticalHeader()
        header_co.setDefaultSectionSize(28)
        header_co.hide()
        self.coberta_table_view.mousePressEvent = lambda e: (setattr(self, '_foco_coberta', True), setattr(self, '_foco_vendidas', False), QTableView.mousePressEvent(self.coberta_table_view, e))[2]
        self.coberta_table_view.doubleClicked.connect(self._on_coberta_row_double_clicked)

        self._aplicar_fonte_tamanho()

        # --- QSplitter ---
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self.table_view)
        self._splitter.addWidget(self.vendidas_table_view)
        self._splitter.addWidget(self.coberta_table_view)
        self._splitter.setSizes([500, 168, 168])

        temas_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent.parent)) / "temas"
        self._splash_movie = None
        self._media_player = None
        mp4_path = temas_dir / "Spreadhunterabertura.mp4"
        gif_path = temas_dir / "Spreadhunterabertura.gif"
        jpg_path = temas_dir / "shtemaabertura.jpeg"
        if mp4_path.exists():
            self._splash_abertura = QVideoWidget()
            self._splash_abertura.setStyleSheet("background-color: #0d0d0d;")
            self._media_player = QMediaPlayer()
            self._media_player.setSource(QUrl.fromLocalFile(str(mp4_path)))
            self._media_player.setVideoOutput(self._splash_abertura)
            self._media_player.setLoops(QMediaPlayer.Loops.Infinite)
            self._media_player.play()
        elif gif_path.exists():
            self._splash_abertura = QLabel()
            self._splash_movie = QMovie(str(gif_path))
            self._splash_movie.setScaledSize(QSize(1200, 600))
            self._splash_abertura.setMovie(self._splash_movie)
            self._splash_abertura.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._splash_abertura.setStyleSheet("background-color: #0d0d0d;")
            self._splash_movie.start()
        else:
            self._splash_abertura = QLabel()
            pix_abertura = QPixmap(str(jpg_path))
            if not pix_abertura.isNull():
                self._splash_abertura.setPixmap(pix_abertura.scaled(1200, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self._splash_abertura.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._splash_abertura.setStyleSheet("background-color: #0d0d0d;")
            else:
                self._splash_abertura.setText("SPREADHUNTER")
                self._splash_abertura.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._splash_abertura.setStyleSheet("color: #4fc3f7; font-size: 36pt; font-weight: bold; background-color: #0d0d0d;")

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
        self._stack.addWidget(self._splash_abertura)
        self._stack.addWidget(self._splash_transicao)
        self._stack.addWidget(self._splitter)
        self._stack.addWidget(self._disclaimer)
        self._stack.setCurrentIndex(0)
        main_layout.addWidget(self._stack, stretch=1)

        self._dashboard_box = QFrame()
        self._dashboard_box.setFrameShape(QFrame.StyledPanel)
        self._dashboard_box.setStyleSheet("background-color: #141428; border: 1px solid #2a2a44; border-radius: 6px; padding: 4px;")
        self._dashboard_layout = QHBoxLayout(self._dashboard_box)
        self._dashboard_layout.setContentsMargins(8, 4, 8, 4)
        self._dashboard_layout.setSpacing(8)
        lbl_dash = QLabel("📊 Séries:")
        lbl_dash.setStyleSheet("color: #8888cc; font-size: 8pt; font-weight: bold; background: transparent; border: none;")
        self._dashboard_layout.addWidget(lbl_dash)
        self._dashboard_layout.addStretch()
        main_layout.addWidget(self._dashboard_box)
        self._stack.currentChanged.connect(lambda idx: self._dashboard_box.setVisible(idx == 2))

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #2d2d44; max-height: 1px;")
        main_layout.addWidget(separator)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)

        _btn_base = (
            "QPushButton {{"
            "  background: transparent;"
            "  border-style: solid; border-radius: 4px;"
            "  padding: 4px 8px; min-height: 26px;"
            "  font-size: 9pt; font-weight: 600;"
            " }}"
        )
        _btn_hover = "QPushButton:hover {{ color: {}; }}".format(Palette.TEXT_PRIMARY)

        self.btn_calc = QPushButton("\U0001f9ee  Calcs")
        self.btn_calc.setAutoDefault(False)
        self.btn_calc.clicked.connect(self._abrir_calculadoras)
        self.btn_calc.setToolTip("Calculadoras: Black-Scholes (preço, IV, gregas, ±2σ) + CDI (valor a investir)")
        self.btn_calc.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #4a90d9; border-color: rgba(74,144,217,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #2d4a7a; border-color: #4a90d9; }}"
        )
        btn_layout.addWidget(self.btn_calc)

        self.btn_workspace = QPushButton("\U0001f4c1  Workspace")
        self.btn_workspace.setAutoDefault(False)
        self.btn_workspace.clicked.connect(self._abrir_workspace)
        self.btn_workspace.setToolTip(
            "Workspace (Ctrl+Shift+S): salvar/restaurar snapshot de parâmetros + ordem de colunas"
        )
        self.btn_workspace.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #b388ff; border-color: rgba(179,136,255,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #3d2d6a; border-color: #b388ff; }}"
        )
        btn_layout.addWidget(self.btn_workspace)

        self.btn_historico_sim = QPushButton("\U0001f4ca  Simulações")
        self.btn_historico_sim.setAutoDefault(False)
        self.btn_historico_sim.clicked.connect(self._abrir_historico_simulacoes)
        self.btn_historico_sim.setToolTip("Histórico de simulações otimizadas (Collar Calendário)")
        self.btn_historico_sim.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #e67e22; border-color: rgba(230,126,34,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #3d2a15; border-color: #e67e22; }}"
        )
        btn_layout.addWidget(self.btn_historico_sim)

        self.btn_paineis = self._criar_dropup_paineis(_btn_base, _btn_hover)
        btn_layout.addWidget(self.btn_paineis)

        self.btn_colar = QPushButton("\U0001f6e1  Collar Tradicional")
        self.btn_colar.setAutoDefault(False)
        self.btn_colar.clicked.connect(self._abrir_colar)
        self.btn_colar.setToolTip("Collar Protetivo (tradicional): PUT OTM + CALL OTM — protecao com participacao")
        self.btn_colar.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #3498db; border-color: rgba(52,152,219,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #1a3a5c; border-color: #3498db; }}"
        )
        btn_layout.addWidget(self.btn_colar)

        self.btn_colar_cal = QPushButton("\U0001f4c5  Collar Calendário")
        self.btn_colar_cal.setAutoDefault(False)
        self.btn_colar_cal.clicked.connect(self._abrir_colar_calendario)
        self.btn_colar_cal.setToolTip("Collar Calendário: PUT longa + PUT curta (ou CALL) — theta positivo")
        self.btn_colar_cal.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #f39c12; border-color: rgba(243,156,18,0.45); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #2d1f0e; border-color: #f39c12; }}"
        )
        btn_layout.addWidget(self.btn_colar_cal)

        self.btn_box = QPushButton("\U0001f4e6  Box 4P")
        self.btn_box.setAutoDefault(False)
        self.btn_box.clicked.connect(self._abrir_box)
        self.btn_box.setToolTip("Box Spread 4 Pontas: arbitragem sintetica livre de risco direcional")
        self.btn_box.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #e74c3c; border-color: rgba(231,76,60,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #3d0e0e; border-color: #e74c3c; }}"
        )
        btn_layout.addWidget(self.btn_box)

        self.btn_put_ratio = QPushButton("\U0001f4c9  Put Ratio")
        self.btn_put_ratio.setAutoDefault(False)
        self.btn_put_ratio.clicked.connect(self._abrir_put_ratio)
        self.btn_put_ratio.setToolTip("Put Ratio Spread: estrategia directional/neutra com credito liquido")
        self.btn_put_ratio.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #27ae60; border-color: rgba(39,174,96,0.5); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #0e3d1e; border-color: #27ae60; }}"
        )
        btn_layout.addWidget(self.btn_put_ratio)

        self.btn_mpp = QPushButton("\U0001f3af  MPP")
        self.btn_mpp.setAutoDefault(False)
        self.btn_mpp.clicked.connect(self._abrir_mpp)
        self.btn_mpp.setToolTip("MPP: Matriz de Priorizacao — score multicriterio das oportunidades")
        self.btn_mpp.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #22c55e; border-color: rgba(34,197,94,0.45); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #0e2d1e; border-color: #22c55e; }}"
        )
        btn_layout.addWidget(self.btn_mpp)

        self.btn_varrer = QPushButton("\u25b6  Ligar")
        self.btn_varrer.setAutoDefault(False)
        self.btn_varrer.setCheckable(True)
        self.btn_varrer.setChecked(False)
        self.btn_varrer.clicked.connect(self._toggle_monitor)
        self.btn_varrer.setToolTip("Iniciar/Parar monitoramento RTD em tempo real")
        self.btn_varrer.setStyleSheet(
            _btn_base
            + "QPushButton {{ color: #27ae60; border-color: rgba(39,174,96,0.45); border-width: 1px; }}"
            + _btn_hover
            + "QPushButton:hover {{ background-color: #1a3d2a; border-color: #27ae60; }}"
            + "QPushButton:checked {{ background-color: #3d0e0e; color: {}; border-color: #e74c3c; }}".format(Palette.TEXT_PRIMARY)
            + "QPushButton:checked:hover {{ background-color: #5d1e1e; border-color: #f06050; }}"
        )
        # btn_varrer é adicionado depois, ao lado do indicador RTD (lado direito da toolbar):
        # btn_layout.addWidget(self.btn_varrer)

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
        self._status_vendidas = QLabel("")
        self._status_vendidas.setStyleSheet("color: #8888ff; font-size: 9pt; font-weight: bold; padding: 0 6px;")
        self._status_coberta = QLabel("")
        self._status_coberta.setStyleSheet("color: #2ecc71; font-size: 9pt; font-weight: bold; padding: 0 6px;")

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

        self.btn_export_box = QPushButton("📥")
        self.btn_export_box.setFixedSize(26, 24)
        self.btn_export_box.setToolTip("Exportar linhas BOX/SBTH (CSV -> clipboard).\nCom linha selecionada: so ela. Sem: todas.")
        self.btn_export_box.setCursor(Qt.PointingHandCursor)
        self.btn_export_box.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2f; color: #8be08b;
                border: 1px solid #8be08b66; border-radius: 4px;
                font-size: 10pt; padding: 0; margin: 0;
                text-align: center;
            }
            QPushButton:hover { background-color: #2d2d44; }
        """)
        self.btn_export_box.clicked.connect(self._exportar_csv_box)
        btn_layout.addWidget(self.btn_export_box)

        self._spin_topn_box = QWidget()
        self._spin_topn_box.setFixedSize(52, 24)
        self._spin_topn_box.setToolTip("0 = mostra todos. 1-N = só as N melhores linhas de cada ativo (coluna de ordenação atual)")
        hb = QHBoxLayout(self._spin_topn_box)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(1)
        self._spin_topn_val = QLabel("0")
        self._spin_topn_val.setFixedSize(22, 22)
        self._spin_topn_val.setAlignment(Qt.AlignCenter)
        self._spin_topn_val.setStyleSheet("QLabel { background-color: #0d0d1a; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 2px; font-size: 7pt; font-weight: bold; }")
        self._spin_topn_minus = QPushButton("-")
        self._spin_topn_minus.setFixedSize(14, 22)
        self._spin_topn_minus.setStyleSheet("QPushButton { background-color: #1a1a2e; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 2px; font-size: 8pt; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #2a2a3e; }")
        self._spin_topn_plus = QPushButton("+")
        self._spin_topn_plus.setFixedSize(14, 22)
        self._spin_topn_plus.setStyleSheet("QPushButton { background-color: #1a1a2e; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 2px; font-size: 8pt; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #2a2a3e; }")
        hb.addWidget(self._spin_topn_minus)
        hb.addWidget(self._spin_topn_val)
        hb.addWidget(self._spin_topn_plus)
        self._spin_topn_n = 0
        self._spin_topn_minus.clicked.connect(lambda: self._set_topn_box(self._spin_topn_n - 1))
        self._spin_topn_plus.clicked.connect(lambda: self._set_topn_box(self._spin_topn_n + 1))
        btn_layout.addWidget(self._spin_topn_box)

        self.btn_bell_v = QPushButton("🔕")
        self.btn_bell_v.setFixedSize(26, 24)
        self.btn_bell_v.setToolTip("Som VENDIDAS: desligado (clique para ligar)")
        self.btn_bell_v.setCursor(Qt.PointingHandCursor)
        self.btn_bell_v.setCheckable(True)
        self.btn_bell_v.setStyleSheet("""
            QPushButton {
                background-color: #3d1a1a; color: #ef4444;
                border: 1px solid #ef4444; border-radius: 4px;
                font-size: 11pt; padding: 0;
            }
            QPushButton:hover { background-color: #5d2a2a; }
            QPushButton:checked {
                background-color: #1a3d1a; color: #22c55e;
                border: 1px solid #e57373;
            }
            QPushButton:checked:hover { background-color: #2a5d2a; }
        """)
        self.btn_bell_v.toggled.connect(self._toggle_som_vendidas)
        btn_layout.addWidget(self.btn_bell_v)

        self.btn_export_vendidas = QPushButton("📥")
        self.btn_export_vendidas.setFixedSize(26, 24)
        self.btn_export_vendidas.setToolTip("Exportar linhas VENDIDAS (CSV -> clipboard).\nCom linha selecionada: so ela. Sem: todas.")
        self.btn_export_vendidas.setCursor(Qt.PointingHandCursor)
        self.btn_export_vendidas.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2f; color: #8be08b;
                border: 1px solid #8be08b66; border-radius: 4px;
                font-size: 10pt; padding: 0; margin: 0;
                text-align: center;
            }
            QPushButton:hover { background-color: #2d2d44; }
        """)
        self.btn_export_vendidas.clicked.connect(self._exportar_csv_vendidas)
        btn_layout.addWidget(self.btn_export_vendidas)

        self._spin_topn_vend = QWidget()
        self._spin_topn_vend.setFixedSize(52, 24)
        self._spin_topn_vend.setToolTip("0 = mostra todos. 1-N = só as N melhores linhas de cada ativo (coluna de ordenação atual)")
        hb = QHBoxLayout(self._spin_topn_vend)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(1)
        self._spin_topn_vend_val = QLabel("0")
        self._spin_topn_vend_val.setFixedSize(22, 22)
        self._spin_topn_vend_val.setAlignment(Qt.AlignCenter)
        self._spin_topn_vend_val.setStyleSheet("QLabel { background-color: #0d0d1a; color: #e57373; "
            "border: 1px solid #8a3a3a; border-radius: 2px; font-size: 7pt; font-weight: bold; }")
        self._spin_topn_vend_minus = QPushButton("-")
        self._spin_topn_vend_minus.setFixedSize(14, 22)
        self._spin_topn_vend_minus.setStyleSheet("QPushButton { background-color: #1a1a2e; color: #e57373; "
            "border: 1px solid #8a3a3a; border-radius: 2px; font-size: 8pt; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #2a2a3e; }")
        self._spin_topn_vend_plus = QPushButton("+")
        self._spin_topn_vend_plus.setFixedSize(14, 22)
        self._spin_topn_vend_plus.setStyleSheet("QPushButton { background-color: #1a1a2e; color: #e57373; "
            "border: 1px solid #8a3a3a; border-radius: 2px; font-size: 8pt; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #2a2a3e; }")
        hb.addWidget(self._spin_topn_vend_minus)
        hb.addWidget(self._spin_topn_vend_val)
        hb.addWidget(self._spin_topn_vend_plus)
        self._spin_topn_vend_n = 0
        self._spin_topn_vend_minus.clicked.connect(lambda: self._set_topn_vend(self._spin_topn_vend_n - 1))
        self._spin_topn_vend_plus.clicked.connect(lambda: self._set_topn_vend(self._spin_topn_vend_n + 1))
        btn_layout.addWidget(self._spin_topn_vend)

        self.btn_bell_c = QPushButton("\U0001f514")
        self.btn_bell_c.setFixedSize(26, 24)
        self.btn_bell_c.setToolTip("Som VENDA COBERTA: desligado (clique para ligar)")
        self.btn_bell_c.setCursor(Qt.PointingHandCursor)
        self.btn_bell_c.setCheckable(True)
        self.btn_bell_c.setStyleSheet("""
            QPushButton {
                background-color: #0d1a2e; color: #42a5f5;
                border: 1px solid #42a5f5; border-radius: 4px;
                font-size: 11pt; padding: 0;
            }
            QPushButton:hover { background-color: #1a2e4a; }
            QPushButton:checked {
                background-color: #0d1a2e; color: #42a5f5;
                border: 1px solid #42a5f5;
            }
            QPushButton:checked:hover { background-color: #1a2e4a; }
        """)
        self.btn_bell_c.toggled.connect(self._toggle_som_coberta)
        btn_layout.addWidget(self.btn_bell_c)

        self.btn_export_coberta = QPushButton("📥")
        self.btn_export_coberta.setFixedSize(26, 24)
        self.btn_export_coberta.setToolTip("Exportar linhas TAXA (CSV -> clipboard).\nCom linha selecionada: so ela. Sem: todas.")
        self.btn_export_coberta.setCursor(Qt.PointingHandCursor)
        self.btn_export_coberta.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2f; color: #8be08b;
                border: 1px solid #8be08b66; border-radius: 4px;
                font-size: 10pt; padding: 0; margin: 0;
                text-align: center;
            }
            QPushButton:hover { background-color: #2d2d44; }
        """)
        self.btn_export_coberta.clicked.connect(self._exportar_csv_coberta)
        btn_layout.addWidget(self.btn_export_coberta)

        self._spin_topn_taxa = QWidget()
        self._spin_topn_taxa.setFixedSize(52, 24)
        self._spin_topn_taxa.setToolTip("0 = mostra todos. 1-N = só as N melhores linhas de cada ativo (coluna de ordenação atual)")
        hb = QHBoxLayout(self._spin_topn_taxa)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(1)
        self._spin_topn_taxa_val = QLabel("0")
        self._spin_topn_taxa_val.setFixedSize(22, 22)
        self._spin_topn_taxa_val.setAlignment(Qt.AlignCenter)
        self._spin_topn_taxa_val.setStyleSheet("QLabel { background-color: #0d0d1a; color: #42a5f5; "
            "border: 1px solid #2a4a7a; border-radius: 2px; font-size: 7pt; font-weight: bold; }")
        self._spin_topn_taxa_minus = QPushButton("-")
        self._spin_topn_taxa_minus.setFixedSize(14, 22)
        self._spin_topn_taxa_minus.setStyleSheet("QPushButton { background-color: #1a1a2e; color: #42a5f5; "
            "border: 1px solid #2a4a7a; border-radius: 2px; font-size: 8pt; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #2a2a3e; }")
        self._spin_topn_taxa_plus = QPushButton("+")
        self._spin_topn_taxa_plus.setFixedSize(14, 22)
        self._spin_topn_taxa_plus.setStyleSheet("QPushButton { background-color: #1a1a2e; color: #42a5f5; "
            "border: 1px solid #2a4a7a; border-radius: 2px; font-size: 8pt; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #2a2a3e; }")
        hb.addWidget(self._spin_topn_taxa_minus)
        hb.addWidget(self._spin_topn_taxa_val)
        hb.addWidget(self._spin_topn_taxa_plus)
        self._spin_topn_taxa_n = 0
        self._spin_topn_taxa_minus.clicked.connect(lambda: self._set_topn_taxa(self._spin_topn_taxa_n - 1))
        self._spin_topn_taxa_plus.clicked.connect(lambda: self._set_topn_taxa(self._spin_topn_taxa_n + 1))
        btn_layout.addWidget(self._spin_topn_taxa)

        btn_layout.addSpacing(16)
        btn_layout.addStretch()

        btn_layout.addWidget(self.btn_varrer)
        self.lbl_rtd_indicator = QLabel(" OFF ")
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

    def _apply_hidden_columns_vendidas(self):
        from PySide6.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = settings.value("colunas_ocultas_vendidas", None)
        if hidden_cols is None:
            return
        if isinstance(hidden_cols, str):
            hidden_cols = hidden_cols.split(",") if hidden_cols else []
        elif not isinstance(hidden_cols, list):
            hidden_cols = list(hidden_cols)
        cols = VendidasTableModel.COLUMNS
        for i, (_, col_key) in enumerate(cols):
            self.vendidas_table_view.setColumnHidden(i, col_key in hidden_cols)

    def _apply_hidden_columns_coberta(self):
        from PySide6.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = settings.value("colunas_ocultas_coberta", None)
        if hidden_cols is None:
            return
        if isinstance(hidden_cols, str):
            hidden_cols = hidden_cols.split(",") if hidden_cols else []
        elif not isinstance(hidden_cols, list):
            hidden_cols = list(hidden_cols)
        cols = VendaCobertaTableModel.COLUMNS
        for i, (_, col_key) in enumerate(cols):
            self.coberta_table_view.setColumnHidden(i, col_key in hidden_cols)

    def _save_column_visibility(self):
        from PySide6.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = []
        for i, (_, col_key) in enumerate(MonitorTableModel.COLUMNS):
            if self.table_view.isColumnHidden(i):
                hidden_cols.append(col_key)
        settings.setValue("colunas_ocultas", hidden_cols)

    def _save_column_visibility_vendidas(self):
        from PySide6.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = []
        cols = VendidasTableModel.COLUMNS
        for i, (_, col_key) in enumerate(cols):
            if self.vendidas_table_view.isColumnHidden(i):
                hidden_cols.append(col_key)
        settings.setValue("colunas_ocultas_vendidas", hidden_cols)

    def _save_column_visibility_coberta(self):
        from PySide6.QtCore import QSettings
        settings = QSettings("Spreadhunter", "DesktopMonitor")
        hidden_cols = []
        cols = VendaCobertaTableModel.COLUMNS
        for i, (_, col_key) in enumerate(cols):
            if self.coberta_table_view.isColumnHidden(i):
                hidden_cols.append(col_key)
        settings.setValue("colunas_ocultas_coberta", hidden_cols)

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

    def _show_column_menu_vendidas(self, pos):
        menu = QMenu(self)
        header = self.vendidas_table_view.horizontalHeader()
        col_actions = {}
        for i, (col_name, _) in enumerate(VendidasTableModel.COLUMNS):
            action = menu.addAction(col_name)
            action.setCheckable(True)
            action.setChecked(not self.vendidas_table_view.isColumnHidden(i))
            col_actions[id(action)] = i
        chosen = menu.exec_(header.mapToGlobal(pos))
        if chosen is not None and id(chosen) in col_actions:
            col_idx = col_actions[id(chosen)]
            self.vendidas_table_view.setColumnHidden(col_idx, not chosen.isChecked())
            self._save_column_visibility_vendidas()

    def _show_column_menu_coberta(self, pos):
        menu = QMenu(self)
        header = self.coberta_table_view.horizontalHeader()
        col_actions = {}
        for i, (col_name, _) in enumerate(VendaCobertaTableModel.COLUMNS):
            action = menu.addAction(col_name)
            action.setCheckable(True)
            action.setChecked(not self.coberta_table_view.isColumnHidden(i))
            col_actions[id(action)] = i
        chosen = menu.exec_(header.mapToGlobal(pos))
        if chosen is not None and id(chosen) in col_actions:
            col_idx = col_actions[id(chosen)]
            self.coberta_table_view.setColumnHidden(col_idx, not chosen.isChecked())
            self._save_column_visibility_coberta()

    def _setup_status_bar(self):
        self._status_left = QLabel("Pronto")
        self._status_left.setProperty("class", "")
        self.statusBar().addWidget(self._status_left, 1)

        self.lbl_count.setVisible(True)
        self._status_colar.setVisible(True)
        self._status_colar_cal.setVisible(True)
        self._status_box.setVisible(True)
        self._status_vendidas.setVisible(True)
        self._status_coberta.setVisible(True)

        for w in (self.lbl_count, self._status_colar, self._status_colar_cal, self._status_box, self._status_vendidas, self._status_coberta):
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
                "padding: 2px 12px; font-weight: bold; font-size: 9pt;".format(Palette.GREEN_DIM)
            )
            self.lbl_rtd_indicator.setText(" RTD: ON ")
        else:
            self.lbl_rtd_indicator.setStyleSheet(
                "background-color: {}; color: {}; border-radius: 4px; "
                "padding: 2px 12px; font-weight: bold; font-size: 9pt;".format(Palette.RED_DIM, Palette.RED)
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
        from src.domain.services.calendario_b3 import dc_to_du, dc_to_du_aproximado
        from PySide6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout,
            QHBoxLayout, QSpinBox, QLabel, QGroupBox, QFormLayout, QPushButton,
        )

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
        dialog.setMinimumSize(440, 520)
        dialog.setStyleSheet("background-color: #0d0d1a; color: #e0e0e0;")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Tabela de Vencimentos ──
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

        # ── Calculadora CDI ──
        cdi_group = QGroupBox("Calculadora CDI")
        cdi_group.setStyleSheet("""
            QGroupBox {
                color: #e0e0e0; font-size: 10pt; font-weight: bold;
                border: 1px solid #2d2d44; border-radius: 6px;
                margin-top: 10px; padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
        """)
        cdi_form = QFormLayout(cdi_group)
        cdi_form.setSpacing(4)
        cdi_form.setContentsMargins(10, 16, 10, 10)

        taxa_label = QLabel(f"<b>{taxa_cdi * 100:.2f}% a.a.</b>")
        taxa_label.setStyleSheet("color: #f0c040; font-size: 10pt; font-family: Consolas;")
        cdi_form.addRow("Taxa CDI:", taxa_label)

        spin_dc = QSpinBox()
        spin_dc.setRange(1, 3650)
        spin_dc.setValue(30)
        spin_dc.setStyleSheet("""
            QSpinBox {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 4px;
                padding: 2px 6px; font-size: 10pt; font-family: Consolas;
            }
        """)
        cdi_form.addRow("Dias Corridos (DC):", spin_dc)

        lbl_du = QLabel("—")
        lbl_du.setStyleSheet("color: #00f2ff; font-size: 10pt; font-family: Consolas;")
        cdi_form.addRow("Dias Úteis (DU):", lbl_du)

        lbl_cdi_dc = QLabel("—")
        lbl_cdi_dc.setStyleSheet("color: #40c040; font-size: 10pt; font-family: Consolas;")
        cdi_form.addRow("CDI (DC/365):", lbl_cdi_dc)

        lbl_cdi_du = QLabel("—")
        lbl_cdi_du.setStyleSheet("color: #40c040; font-size: 10pt; font-family: Consolas;")
        cdi_form.addRow("CDI (DU/252):", lbl_cdi_du)

        def _calcular():
            dc_val = spin_dc.value()
            du_val = dc_to_du_aproximado(dc_val)
            cdi_du_val = (1 + taxa_cdi) ** (du_val / 252) - 1
            cdi_dc_val = (1 + taxa_cdi) ** (dc_val / 365) - 1
            lbl_du.setText(str(du_val))
            lbl_cdi_dc.setText(f"{cdi_dc_val * 100:.4f}%")
            lbl_cdi_du.setText(f"{cdi_du_val * 100:.4f}%")

        spin_dc.valueChanged.connect(_calcular)
        _calcular()

        layout.addWidget(cdi_group)

        # ── Fechar ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_fechar)
        layout.addLayout(btn_layout)

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
        if not hasattr(self, '_worker'):
            return
        if self._foco_coberta:
            tracker = getattr(self._worker._monitor_coberta_uc, '_ultimo_pipeline', None)
        elif self._foco_vendidas:
            tracker = getattr(self._worker._monitor_vendidas_uc, '_ultimo_pipeline', None)
        else:
            tracker = getattr(self._worker._monitor_uc, '_ultimo_pipeline', None)
        dlg = PipelineDialog(tracker, self)
        dlg.exec_()

    def _abrir_parametros(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Parametros Operacionais")
        dialog.setMinimumSize(820, 660)
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
        self._aplicar_fonte_tamanho()
        self._update_cdi_display()

    def _abrir_workspace(self):
        try:
            from src.application.services.workspace_service import WorkspaceService
            from src.ui.desktop.workspace_dialog import WorkspaceDialog
            service = WorkspaceService(db_path=self.db_path)
            service.garantir_system_default()
            dlg = WorkspaceDialog(service, parent=self)
            dlg.restaurar_solicitado.connect(self._on_workspace_restaurado)
            dlg.exec_()
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Workspace", f"Falha ao abrir o diálogo:\n{e}")
            except Exception:
                pass

    def _on_workspace_restaurado(self, snapshot_id: str):
        self._worker.recarregar_parametros()
        self._aplicar_tema_configurado()
        self._aplicar_fonte_tamanho()
        self._update_cdi_display()

    def _abrir_historico_simulacoes(self):
        try:
            from src.ui.desktop.historico_simulacoes_dialog import HistoricoSimulacoesDialog
            dlg = HistoricoSimulacoesDialog(parent=self)
            dlg.exec_()
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Simulações", f"Falha ao abrir histórico:\n{e}")
            except Exception:
                pass

    def _abrir_estudos_calendario(self):
        try:
            from src.ui.desktop.estudos_calendario_dialog import EstudosCalendarioDialog
            dlg = EstudosCalendarioDialog(parent=self)
            dlg.exec_()
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Estudos", f"Falha ao abrir estudos:\n{e}")
            except Exception:
                pass

    def _on_fade_finished(self):
        self._transicao_opacity.setOpacity(1.0)
        if self._stack.currentIndex() == 1:
            self._stack.setCurrentIndex(3)

    def _fechar_disclaimer(self):
        self._stack.setCurrentIndex(2)

    def _toggle_monitor(self, checked):
        if checked:
            if self._media_player:
                self._media_player.pause()
            elif self._splash_movie:
                self._splash_movie.stop()
            self._stack.setCurrentIndex(1)
            QTimer.singleShot(1500, self._fade_anim.start)
            self.btn_varrer.setText("\u25a0  Desligar")
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
            if self._media_player:
                self._media_player.play()
            elif self._splash_movie:
                self._splash_movie.start()
            self._transicao_opacity.setOpacity(1.0)
            self.btn_varrer.setText("\u25b6  Ligar")
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

    def _set_topn_box(self, n: int):
        self._spin_topn_n = max(0, min(9, n))
        self._spin_topn_val.setText(str(self._spin_topn_n))
        self._main_proxy.set_top_n(self._spin_topn_n)

    def _set_topn_vend(self, n: int):
        self._spin_topn_vend_n = max(0, min(9, n))
        self._spin_topn_vend_val.setText(str(self._spin_topn_vend_n))
        self._vend_proxy.set_top_n(self._spin_topn_vend_n)

    def _set_topn_taxa(self, n: int):
        self._spin_topn_taxa_n = max(0, min(9, n))
        self._spin_topn_taxa_val.setText(str(self._spin_topn_taxa_n))
        self._taxa_proxy.set_top_n(self._spin_topn_taxa_n)

    def _on_rtd_status(self, connected: bool):
        self._rtd_connected = connected
        self._update_rtd_indicator(connected)
        if self._colar_dialog and self._colar_dialog.isVisible():
            self._colar_dialog.set_rtd_status(connected)

        if connected and hasattr(self, 'top_bar'):
            source = self._worker.market_data_source if hasattr(self._worker, 'market_data_source') else None
            if source:
                self.top_bar.conectar_fonte(source)

    def _on_oportunidades_atualizadas(self, resultados: list):
        self._resultados_brutos = resultados
        self._filtrar_e_atualizar_tabela()

    def _on_oportunidades_vendidas_atualizadas(self, resultados: list):
        self._resultados_vendidas = resultados
        self._filtrar_e_atualizar_vendidas()
        self._atualizar_dashboard()

    def _on_oportunidades_coberta_atualizadas(self, resultados: list):
        self._resultados_coberta = resultados
        self._filtrar_e_atualizar_coberta()
        self._atualizar_dashboard()

    def _filtrar_e_atualizar_vendidas(self):
        if self._filtro_vencimento_vendidas:
            filtrados = [r for r in self._resultados_vendidas if self._key_vencimento_vendida(r) == self._filtro_vencimento_vendidas]
        else:
            filtrados = self._resultados_vendidas
        self.vendidas_model.atualizar(filtrados)
        self._vend_proxy.invalidate_top_n()
        n = len(filtrados)
        viaveis = sum(1 for r in filtrados if r.viavel)
        self._status_vendidas.setText(f"\U0001f4c9 {n} ({viaveis} viav)" if n else "")
        if self._som_vendidas_ativado and viaveis > 0:
            from src.infrastructure.services.som_service import tocar_vendidas
            tocar_vendidas(self.db_path)

    def _key_vencimento_coberta(self, r) -> str:
        raw = r.vencimento.strftime("%d/%m/%y") if hasattr(r.vencimento, "strftime") else str(r.vencimento)
        cod = r.cod_put or r.cod_call
        prefix = "S-" if MainWindow._is_weekly(cod) else ""
        return f"{prefix}{raw}"

    def _filtrar_e_atualizar_coberta(self):
        if self._filtro_vencimento_coberta:
            filtrados = [r for r in self._resultados_coberta if self._key_vencimento_coberta(r) == self._filtro_vencimento_coberta]
        else:
            filtrados = self._resultados_coberta
        self.coberta_model.atualizar(filtrados)
        self._taxa_proxy.invalidate_top_n()
        n = len(filtrados)
        viaveis = sum(1 for r in filtrados if r.viavel)
        self._status_coberta.setText(f"\U0001f4c9 {n} ({viaveis} viav)" if n else "")
        if self._som_coberta_ativado and viaveis > 0:
            from src.infrastructure.services.som_service import tocar_coberta
            tocar_coberta(self.db_path)

    def _key_vencimento_vendida(self, r) -> str:
        raw = r.vencimento.strftime("%d/%m/%y") if hasattr(r.vencimento, "strftime") else str(r.vencimento)
        cod = r.cod_put or r.cod_call
        prefix = "S-" if MainWindow._is_weekly(cod) else ""
        return f"{prefix}{raw}"

    def _filtrar_e_atualizar_tabela(self):
        if self._filtro_vencimento:
            filtrados = [r for r in self._resultados_brutos if self._key_vencimento(r) == self._filtro_vencimento]
        else:
            filtrados = self._resultados_brutos
        self.table_model.atualizar(filtrados)
        self._main_proxy.invalidate_top_n()
        self._total_opps = len(filtrados)
        self._total_viaveis = sum(1 for r in filtrados if r.viavel)
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
            from src.infrastructure.services.som_service import tocar
            tocar(self.db_path)

        self._atualizar_dashboard()

    @staticmethod
    def _is_weekly(cod: str) -> bool:
        if len(cod) < 5:
            return False
        c = cod[4].upper()
        return c in ("A", "B", "C", "D", "M", "N", "O", "P")

    def _key_vencimento(self, r) -> str:
        raw = r.vencimento.strftime("%d/%m/%y") if hasattr(r.vencimento, "strftime") else str(r.vencimento)
        cod = r.cod_put or r.cod_call
        prefix = "S-" if self._is_weekly(cod) else ""
        return f"{prefix}{raw}"

    def _filtrar_por_vencimento(self, key: str | None):
        if self._foco_coberta:
            self._filtro_vencimento_coberta = key
            self._filtrar_e_atualizar_coberta()
        elif self._foco_vendidas:
            self._filtro_vencimento_vendidas = key
            self._filtrar_e_atualizar_vendidas()
        else:
            self._filtro_vencimento = key
            self._filtrar_e_atualizar_tabela()

    @staticmethod
    def _dashboard_sort_key(data: str):
        raw = data[2:] if data.startswith("S-") else data
        try:
            dt = datetime.strptime(raw, "%d/%m/%y")
        except ValueError:
            return (datetime.max, 1)
        return (dt, 0 if data.startswith("S-") else 1)

    def _atualizar_dashboard(self):
        count_c: Counter = Counter()
        for r in self._resultados_brutos:
            count_c[self._key_vencimento(r)] += 1
        count_v: Counter = Counter()
        for r in self._resultados_vendidas:
            count_v[self._key_vencimento_vendida(r)] += 1
        count_co: Counter = Counter()
        for r in self._resultados_coberta:
            count_co[self._key_vencimento_coberta(r)] += 1

        todas = set(count_c) | set(count_v) | set(count_co)

        while self._dashboard_layout.count() > 2:
            item = self._dashboard_layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()

        total_c = sum(count_c.values())
        total_v = sum(count_v.values())
        total_co = sum(count_co.values())
        total_t = total_c + total_v + total_co

        def _badge(texto, cor_bg, cor_fg, cor_borda, ativo=False):
            b = QPushButton(texto)
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {cor_bg}; color: {cor_fg};
                    border: {'2px solid ' + cor_fg if ativo else '1px solid ' + cor_borda};
                    border-radius: 4px; padding: 2px 6px;
                    font-size: 8pt; font-weight: bold;
                }}
                QPushButton:hover {{ border: 1px solid {cor_fg}; }}
            """)
            return b

        b = _badge(f" TOTAL  {total_t} ", "#1a1a3e", "#8888ff", "#2a2a5e")
        b.clicked.connect(lambda: self._filtrar_por_vencimento(None))
        self._dashboard_layout.insertWidget(self._dashboard_layout.count() - 1, b)

        for data in sorted(todas, key=self._dashboard_sort_key):
            qc = count_c.get(data, 0)
            qv = count_v.get(data, 0)
            qco = count_co.get(data, 0)
            display_date = data[2:] if data.startswith("S-") else data
            tipo = "S" if data.startswith("S-") else "M"
            ativo = (data == self._filtro_vencimento) or (data == self._filtro_vencimento_vendidas) or (data == self._filtro_vencimento_coberta)
            b = _badge(f" {display_date}  {tipo} ({qc}C {qv}V) ", "#1e3a1e", "#4caf50", "#2e5a2e", ativo)
            b.clicked.connect(lambda checked, k=data: self._filtrar_por_vencimento(k))
            self._dashboard_layout.insertWidget(self._dashboard_layout.count() - 1, b)

    def _toggle_som_global(self, ativo: bool):
        self._som_ativado = ativo
        self.btn_bell.setToolTip("Som: ligado" if ativo else "Som: desligado")

    def _toggle_som_vendidas(self, ativo: bool):
        self._som_vendidas_ativado = ativo
        self.btn_bell_v.setToolTip("Som VENDIDAS: ligado" if ativo else "Som VENDIDAS: desligado")

    def _exportar_csv_box(self):
        from src.ui.desktop.copy_utils import exportar_monitor_csv
        from src.ui.desktop.monitor_table_model import MonitorTableModel
        exportar_monitor_csv(
            resultados=self._resultados_brutos,
            colunas=MonitorTableModel.COLUMNS,
            table_view=self.table_view,
            parent=self,
            titulo_janela="Export CSV - BOX/SBTH",
        )

    def _toggle_som_coberta(self, ativo: bool):
        self._som_coberta_ativado = ativo
        self.btn_bell_c.setToolTip("Som VENDA COBERTA: ligado" if ativo else "Som VENDA COBERTA: desligado")

    def _exportar_csv_vendidas(self):
        from src.ui.desktop.copy_utils import exportar_monitor_csv
        from src.ui.desktop.vendidas_table_model import VendidasTableModel
        exportar_monitor_csv(
            resultados=self._resultados_vendidas,
            colunas=VendidasTableModel.COLUMNS,
            table_view=self.vendidas_table_view,
            parent=self,
            titulo_janela="Export CSV - VENDIDAS",
        )

    def _exportar_csv_coberta(self):
        from src.ui.desktop.copy_utils import exportar_monitor_csv
        from src.ui.desktop.venda_coberta_table_model import VendaCobertaTableModel
        exportar_monitor_csv(
            resultados=self._resultados_coberta,
            colunas=VendaCobertaTableModel.COLUMNS,
            table_view=self.coberta_table_view,
            parent=self,
            titulo_janela="Export CSV - TAXA",
        )

    def _aplicar_fonte_tamanho(self):
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self.db_path)
        p = repo.get_by_chave("fonte_tamanho")
        tamanho = int(p.valor) if p else 9
        tamanho = max(8, min(16, tamanho))
        font = QFont("Consolas", tamanho)
        self.table_view.setFont(font)
        self.vendidas_table_view.setFont(font)
        self.coberta_table_view.setFont(font)
        # Aplica no header stylesheet também
        for h, cor in [(self.table_view.horizontalHeader(), "#4caf50"),
                        (self.vendidas_table_view.horizontalHeader(), "#e57373"),
                        (self.coberta_table_view.horizontalHeader(), "#42a5f5")]:
            h.setStyleSheet(
                "QHeaderView::section {{ background-color: #1e1e1e; color: {}; "
                "font-weight: bold; font-size: {}pt; padding: 4px 8px; border: 1px solid #333; }}".format(cor, tamanho)
            )

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

    def _abrir_calculadoras(self):
        from src.ui.desktop.calculadoras_dialog import CalculadorasDialog
        dlg = CalculadorasDialog(self.db_path, self)
        dlg.exec_()

    def _abrir_importflash(self):
        from src.ui.desktop.grade_opcoes_dialog import GradeOpcoesDialog
        dialog = GradeOpcoesDialog(
            self.db_path,
            self,
            on_import_concluido=self._on_importflash_concluido,
        )
        dialog.exec_()
        # Após fechar, garante recarga dos instrumentos no worker
        self._worker.recarregar_instrumentos()

    def _on_importflash_concluido(self, exit_code: int):
        """Callback chamado pelo GradeOpcoesDialog quando importflash termina."""
        self._status_left.setText("ImportFlash: concluído com sucesso!")
        self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))

    def _abrir_historico(self):
        from src.ui.desktop.historico_dialog import HistoricoDialog
        dialog = HistoricoDialog(self.db_path, self)
        dialog.exec_()

    def _abrir_dividendos(self):
        from src.ui.desktop.dividendos_dialog import DividendosDialog
        dialog = DividendosDialog(self.db_path, self)
        dialog.exec_()

    def _abrir_resultados(self):
        from src.ui.desktop.calendario_resultados_dialog import CalendarioResultadosDialog
        dialog = CalendarioResultadosDialog(self.db_path, self)
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

    def _on_put_ratio_atualizados(self, resultados: list):
        self._ultimos_put_ratio = resultados
        if self._put_ratio_dialog and self._put_ratio_dialog.isVisible():
            self._put_ratio_dialog.atualizar_resultados(resultados)

    def _abrir_put_ratio(self):
        from src.ui.desktop.put_ratio_dialog import PutRatioDialog
        if self._put_ratio_dialog and self._put_ratio_dialog.isVisible():
            self._put_ratio_dialog.raise_()
            return
        self._put_ratio_dialog = PutRatioDialog(self, self.db_path)
        self._put_ratio_dialog.iniciar_scan_signal.connect(self._worker.iniciar_auto_put_ratio)
        self._put_ratio_dialog.parar_scan_signal.connect(self._on_parar_put_ratio)
        self._put_ratio_dialog.atualizar_resultados(self._ultimos_put_ratio)
        self._put_ratio_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._put_ratio_dialog.destroyed.connect(lambda: setattr(self, "_put_ratio_dialog", None))
        self._put_ratio_dialog.show()

    def _on_parar_put_ratio(self):
        self._worker.parar_auto_put_ratio()

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

    def _on_vendidas_row_double_clicked(self, index):
        src_idx = self.vendidas_table_view.model().mapToSource(index) if hasattr(self.vendidas_table_view.model(), 'mapToSource') else index
        row = src_idx.row()
        if row < 0 or row >= len(self._resultados_vendidas):
            return
        r = self._resultados_vendidas[row]
        self._mostrar_detalhes_vendida(r)

    def _on_coberta_row_double_clicked(self, index):
        src_idx = self.coberta_table_view.model().mapToSource(index) if hasattr(self.coberta_table_view.model(), 'mapToSource') else index
        row = src_idx.row()
        if row < 0 or row >= len(self._resultados_coberta):
            return
        r = self._resultados_coberta[row]
        self._mostrar_detalhes_coberta(r)

    def _mostrar_detalhes_vendida(self, r):
        from src.ui.desktop.theme import Palette
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFormLayout, QFrame, QTabWidget, QWidget
        from PySide6.QtGui import QFont
        from PySide6.QtCore import Qt

        dialog = QDialog(self, Qt.Window)
        strategy = "BOX VENDIDO" if r.classificacao == "BOX_VENDIDO" else "SBTH VENDIDA"
        dialog.setWindowTitle("Exportar Operação - {} {}".format(r.ativo, strategy))
        dialog.setMinimumWidth(520)
        dialog.setMinimumHeight(500)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        header = QLabel("{}  |  {}  |  Strike {:.2f}  |  {} ({} DTE)".format(
            r.ativo, r.label_tipo, r.strike,
            r.vencimento.strftime("%d/%m/%Y") if hasattr(r.vencimento, "strftime") else str(r.vencimento),
            r.dias,
        ))
        header.setStyleSheet("font-size: 13pt; font-weight: bold; color: {}; padding: 6px 0;".format(Palette.TEXT_PRIMARY))
        layout.addWidget(header)

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        # --- Tab 1: Pernas & Custos ---
        pernas_widget = QWidget()
        pernas_layout = QVBoxLayout(pernas_widget)
        pernas_layout.setContentsMargins(8, 12, 8, 8)

        from PySide6.QtWidgets import QGroupBox, QFormLayout

        g1 = QGroupBox("Pernas da Estrutura")
        f1 = QFormLayout()
        f1.setSpacing(8)

        def _muted(t):
            l = QLabel(t)
            l.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_SECONDARY))
            return l

        f1.addRow(_muted("Venda Ativo ({})".format(r.ativo)), QLabel("R$ {:.2f} (of. compra)".format(r.preco_ativo)))
        f1.addRow(_muted("Compra Put ({})".format(r.cod_put)), QLabel("R$ {:.2f} (of. compra)  Strike: {:.2f}".format(r.of_compra_put, r.strike)))
        if r.classificacao == "BOX_VENDIDO" and r.cod_call:
            f1.addRow(_muted("Venda Call ({})".format(r.cod_call)), QLabel("R$ {:.2f} (of. venda)  Strike: {:.2f}".format(r.of_venda_call, r.strike)))
        g1.setLayout(f1)
        pernas_layout.addWidget(g1)

        g2 = QGroupBox("Resultado")
        f2 = QFormLayout()
        f2.setSpacing(8)

        lucro = r.recebimento - r.strike
        f2.addRow(_muted("Recebimento:"), QLabel("R$ {:.2f}".format(r.recebimento)))
        f2.addRow(_muted("Lucro (Receb. − Strike):"), QLabel("R$ {:.2f}".format(lucro)))
        if r.custo > 0:
            pnl_final = lucro - r.custo
            f2.addRow(_muted("− Custos B3:"), QLabel("−R$ {:.2f}".format(r.custo)))
            f2.addRow(_muted("= Pós-B3:"), QLabel("R$ {:.2f}".format(pnl_final)))
        pct_liq = getattr(r, 'pct_ganho_liquido', r.pct_ganho) or r.pct_ganho
        cdi_liq = getattr(r, 'pct_cdi_liquido', r.pct_cdi) or r.pct_cdi
        f2.addRow(_muted("Retorno Bruto:"), QLabel("{:.2f}% / {:.2f}x CDI".format(r.pct_ganho * 100, r.pct_cdi)))
        f2.addRow(_muted("Retorno Líq. (B3+IR):"), QLabel("{:.2f}% / {:.2f}x CDI".format(pct_liq * 100, cdi_liq)))

        from datetime import datetime
        from zoneinfo import ZoneInfo
        det = getattr(r, "detectado_em", None)
        det_txt = "-"
        if isinstance(det, datetime):
            if det.tzinfo is None:
                det = det.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
            det_txt = det.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S (Brasília)")
        elif det is not None:
            det_txt = str(det)
        det_lbl = QLabel(det_txt)
        det_lbl.setStyleSheet("color: {}; font-family: Consolas, monospace; font-size: 9pt;".format(Palette.TEXT_SECONDARY))
        f2.addRow(_muted("Detectado:"), det_lbl)

        g2.setLayout(f2)
        pernas_layout.addWidget(g2)
        pernas_layout.addStretch()
        tabs.addTab(pernas_widget, "Pernas & Custos")

        # --- Tab 2: Dados de Mercado ---
        mercado_widget = QWidget()
        mercado_layout = QVBoxLayout(mercado_widget)
        mercado_layout.setContentsMargins(8, 12, 8, 8)

        g3 = QGroupBox("Ofertas")
        f3 = QFormLayout()
        f3.setSpacing(8)
        f3.addRow(_muted("Preço Ativo:"), QLabel("R$ {:.2f}".format(r.preco_ativo)))
        f3.addRow(_muted("Of. Compra PUT:"), QLabel("R$ {:.2f}".format(r.of_compra_put)))
        if r.classificacao == "BOX_VENDIDO":
            f3.addRow(_muted("Of. Venda CALL:"), QLabel("R$ {:.2f}".format(r.of_venda_call)))
        g3.setLayout(f3)
        mercado_layout.addWidget(g3)

        g4 = QGroupBox("Liquidez & Quantidade")
        f4 = QFormLayout()
        f4.setSpacing(8)
        liq_put_ok = r.liq_put_x_lote >= 0
        ll = QLabel("{:.0f}".format(r.liq_put_x_lote))
        ll.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN if liq_put_ok else Palette.RED))
        f4.addRow(_muted("Liq Put x Lote:"), ll)
        if r.classificacao == "BOX_VENDIDO":
            liq_call_ok = r.liq_call_x_lote >= 0
            lc = QLabel("{:.0f}".format(r.liq_call_x_lote))
            lc.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN if liq_call_ok else Palette.RED))
            f4.addRow(_muted("Liq Call x Lote:"), lc)
        f4.addRow(_muted("Qtd PUT:"), QLabel("{:.0f}".format(r.qul_put)))
        if r.classificacao == "BOX_VENDIDO":
            f4.addRow(_muted("Qtd CALL:"), QLabel("{:.0f}".format(r.qul_call)))
        g4.setLayout(f4)
        mercado_layout.addWidget(g4)

        g5 = QGroupBox("Moneyness & Status")
        f5 = QFormLayout()
        f5.setSpacing(8)
        f5.addRow(_muted("Money PUT:"), QLabel("R$ {:.2f}".format(r.money_put)))
        if r.classificacao == "BOX_VENDIDO":
            f5.addRow(_muted("Money CALL:"), QLabel("R$ {:.2f}".format(r.money_call)))
        status_lbl = QLabel("⚠️ LEILÃO" if r.em_leilao else "✓ Aberto")
        if r.em_leilao:
            status_lbl.setStyleSheet("color: #ffffff; background-color: {}; border-radius: 3px; padding: 2px 8px; font-weight: bold;".format(Palette.RED_DIM))
        else:
            status_lbl.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
        f5.addRow(_muted("Status:"), status_lbl)
        g5.setLayout(f5)
        mercado_layout.addWidget(g5)
        mercado_layout.addStretch()
        tabs.addTab(mercado_widget, "Dados de Mercado")

        # --- Botões ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_pnt = QPushButton("\U0001f4cb Basket PNT")
        btn_pnt.setProperty("class", "primary")
        btn_pnt.clicked.connect(lambda: self._abrir_boleta_vendida(r))
        btn_row.addWidget(btn_pnt)

        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)

        dialog.exec_()

    def _abrir_boleta_vendida(self, r):
        strategy = "BOX VENDIDO" if r.classificacao == "BOX_VENDIDO" else "SBTH VENDIDA"
        from src.ui.desktop.boleta_dialog import BoletaDialog
        dlg = BoletaDialog(strategy, r, self.db_path, self)
        dlg.exec_()

    def _mostrar_detalhes_coberta(self, r):
        from src.ui.desktop.theme import Palette
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFormLayout, QFrame, QTabWidget, QWidget, QGroupBox
        from PySide6.QtCore import Qt

        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle("Exportar Operação - {} (TAXA)".format(r.ativo))
        dialog.setMinimumWidth(520)
        dialog.setMinimumHeight(480)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        header = QLabel("{}  |  {}  |  Strike {:.2f}  |  {} ({} DTE)".format(
            r.ativo, r.label_tipo, r.strike,
            r.vencimento.strftime("%d/%m/%Y") if hasattr(r.vencimento, "strftime") else str(r.vencimento),
            r.dias,
        ))
        header.setStyleSheet("font-size: 13pt; font-weight: bold; color: {}; padding: 6px 0;".format(Palette.TEXT_PRIMARY))
        layout.addWidget(header)

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        def _muted(t):
            l = QLabel(t)
            l.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_SECONDARY))
            return l

        # --- Tab 1: Pernas & Custos ---
        pw = QWidget()
        pl = QVBoxLayout(pw)
        pl.setContentsMargins(8, 12, 8, 8)

        g1 = QGroupBox("Pernas da Estrutura")
        f1 = QFormLayout()
        f1.setSpacing(8)
        f1.addRow(_muted("Venda Ativo ({})".format(r.ativo)), QLabel("R$ {:.2f} (of. compra)".format(r.preco_ativo)))
        f1.addRow(_muted("Venda Call ({})".format(r.cod_call)), QLabel("R$ {:.2f} (of. venda)  Strike: {:.2f}".format(r.of_venda_call, r.strike)))
        g1.setLayout(f1)
        pl.addWidget(g1)

        g2 = QGroupBox("Resultado")
        f2 = QFormLayout()
        f2.setSpacing(8)
        lucro = r.recebimento - r.strike
        f2.addRow(_muted("Recebimento:"), QLabel("R$ {:.2f}".format(r.recebimento)))
        f2.addRow(_muted("Lucro (Receb. − Strike):"), QLabel("R$ {:.2f}".format(lucro)))
        if r.custo > 0:
            pnl_final = lucro - r.custo
            f2.addRow(_muted("− Custos B3:"), QLabel("−R$ {:.2f}".format(r.custo)))
            f2.addRow(_muted("= Pós-B3:"), QLabel("R$ {:.2f}".format(pnl_final)))
        pct_liq_cob = getattr(r, 'pct_ganho_liquido', r.pct_ganho) or r.pct_ganho
        cdi_liq_cob = getattr(r, 'pct_cdi_liquido', r.pct_cdi) or r.pct_cdi
        f2.addRow(_muted("Retorno Bruto:"), QLabel("{:.2f}% / {:.2f}x CDI".format(r.pct_ganho * 100, r.pct_cdi)))
        f2.addRow(_muted("Retorno Líq. (B3+IR):"), QLabel("{:.2f}% / {:.2f}x CDI".format(pct_liq_cob * 100, cdi_liq_cob)))

        from datetime import datetime
        from zoneinfo import ZoneInfo
        det = getattr(r, "detectado_em", None)
        det_txt = "-"
        if isinstance(det, datetime):
            if det.tzinfo is None:
                det = det.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
            det_txt = det.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S (Brasília)")
        elif det is not None:
            det_txt = str(det)
        det_lbl = QLabel(det_txt)
        det_lbl.setStyleSheet("color: {}; font-family: Consolas, monospace; font-size: 9pt;".format(Palette.TEXT_SECONDARY))
        f2.addRow(_muted("Detectado:"), det_lbl)

        g2.setLayout(f2)
        pl.addWidget(g2)
        pl.addStretch()
        tabs.addTab(pw, "Pernas & Custos")

        # --- Tab 2: Dados de Mercado ---
        mw = QWidget()
        ml = QVBoxLayout(mw)
        ml.setContentsMargins(8, 12, 8, 8)

        g3 = QGroupBox("Ofertas")
        f3 = QFormLayout()
        f3.setSpacing(8)
        f3.addRow(_muted("Preço Ativo:"), QLabel("R$ {:.2f}".format(r.preco_ativo)))
        f3.addRow(_muted("Of. Venda CALL:"), QLabel("R$ {:.2f}".format(r.of_venda_call)))
        g3.setLayout(f3)
        ml.addWidget(g3)

        g4 = QGroupBox("Liquidez & Quantidade")
        f4 = QFormLayout()
        f4.setSpacing(8)
        liq_ok = r.liq_call_x_lote >= 0
        ll = QLabel("{:.0f}".format(r.liq_call_x_lote))
        ll.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN if liq_ok else Palette.RED))
        f4.addRow(_muted("Liq Call x Lote:"), ll)
        f4.addRow(_muted("Qtd CALL:"), QLabel("{:.0f}".format(r.qul_call)))
        g4.setLayout(f4)
        ml.addWidget(g4)

        g5 = QGroupBox("Moneyness & Status")
        f5 = QFormLayout()
        f5.setSpacing(8)
        f5.addRow(_muted("Money CALL:"), QLabel("R$ {:.2f}".format(r.money_call)))
        status_lbl = QLabel("⚠️ LEILÃO" if r.em_leilao else "✓ Aberto")
        if r.em_leilao:
            status_lbl.setStyleSheet("color: #ffffff; background-color: {}; border-radius: 3px; padding: 2px 8px; font-weight: bold;".format(Palette.RED_DIM))
        else:
            status_lbl.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
        f5.addRow(_muted("Status:"), status_lbl)
        g5.setLayout(f5)
        ml.addWidget(g5)
        ml.addStretch()
        tabs.addTab(mw, "Dados de Mercado")

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_pnt = QPushButton("\U0001f4cb Basket PNT")
        btn_pnt.setProperty("class", "primary")
        btn_pnt.clicked.connect(lambda: self._abrir_boleta_coberta(r))
        btn_row.addWidget(btn_pnt)
        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)

        dialog.exec_()

    def _abrir_boleta_coberta(self, r):
        from src.ui.desktop.boleta_dialog import BoletaDialog
        dlg = BoletaDialog("TAXA", r, self.db_path, self)
        dlg.exec_()

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

    def _abrir_coletar_taxa_aluguel(self):
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository, TaxaAluguelRepository
        param_repo = ParametroRepository(self.db_path)
        habilitado = param_repo.get_by_chave("taxa_aluguel_habilitado")
        if not habilitado or float(habilitado.valor) == 0.0:
            QMessageBox.warning(
                self,
                "Taxa de Aluguel",
                "A coleta de taxas de aluguel está desabilitada nos Parâmetros (taxa_aluguel_habilitado = 0)."
            )
            return

        taxa_repo = TaxaAluguelRepository(self.db_path)
        dados = taxa_repo.get_latest_all()
        if dados:
            self._abrir_visualizar_taxas()
            return

        reply = QMessageBox.question(
            self,
            "Taxa de Aluguel",
            "Nenhuma taxa de aluguel cadastrada no banco.\n\nDeseja coletar agora do site InvestSite?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_taxa_aluguel.setEnabled(False)
        self.btn_taxa_aluguel.setText("⏳ Coletando...")
        self._status_left.setText("InvestSite: Iniciando coleta das taxas de aluguel...")
        self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.YELLOW))

        class _ColetaTaxaThread(QThread):
            finished = Signal(dict)
            progress = Signal(int, int, str)

            def __init__(self, db_path):
                super().__init__()
                self.db_path = db_path

            def run(self):
                from src.application.use_cases.coletar_taxas_aluguel import ColetarTaxasAluguelUseCase
                def cb(corrente, total, ativo):
                    self.progress.emit(corrente, total, ativo)
                
                try:
                    use_case = ColetarTaxasAluguelUseCase(self.db_path)
                    resumo = use_case.executar(callback_progresso=cb)
                except Exception as e:
                    resumo = {"status": "erro", "sucessos": 0, "falhas": 0, "erros": [str(e)]}
                self.finished.emit(resumo)

        self._coleta_thread = _ColetaTaxaThread(self.db_path)
        self._coleta_thread.progress.connect(
            lambda corr, tot, ativo: self._status_left.setText(
                f"InvestSite: Coletando {ativo} ({corr}/{tot})..."
            )
        )
        self._coleta_thread.finished.connect(self._on_coleta_taxa_finished)
        self._coleta_thread.start()

    def _on_coleta_taxa_finished(self, resumo: dict):
        self.btn_taxa_aluguel.setEnabled(True)
        self.btn_taxa_aluguel.setText("\U0001f3e6  Tx Alug.")

        status = resumo.get("status", "sucesso")
        if status == "sucesso":
            sucessos = resumo.get("sucessos", 0)
            falhas = resumo.get("falhas", 0)
            self._status_left.setText(
                "InvestSite: Coleta de taxas conclu\u00edda ({} sucessos / {} falhas).".format(sucessos, falhas)
            )
            self._status_left.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.GREEN)
            )
            QMessageBox.information(
                self, "Taxa de Aluguel",
                "Coleta conclu\u00edda: {} sucessos, {} falhas.".format(sucessos, falhas),
            )
            self._abrir_visualizar_taxas()
        else:
            self._status_left.setText("InvestSite: Erro ao coletar taxas.")
            self._status_left.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.RED)
            )
            erros = resumo.get("erros", ["Erro desconhecido"])
            QMessageBox.critical(self, "Taxa de Aluguel", "A coleta falhou:\n{}".format(erros[0]))

    def _abrir_visualizar_taxas(self):
        from src.infrastructure.persistence.repositories.repositories import TaxaAluguelRepository
        from src.ui.desktop.taxa_aluguel_dialog import TaxaAluguelDialog

        repo = TaxaAluguelRepository(self.db_path)
        dados = repo.get_latest_all()
        if not dados:
            QMessageBox.information(self, "Taxa de Aluguel", "Nenhuma taxa de aluguel cadastrada.\n\nClique em Tx Aluguel para coletar do InvestSite.")
            return

        dlg = TaxaAluguelDialog(self.db_path, self)
        dlg.exec_()

    def _atualizar_tudo(self):
        self.btn_atualizar_tudo.setEnabled(False)
        self.btn_atualizar_tudo.setText("⏳ Atualizando...")
        self.btn_importflash.setEnabled(False)
        self.btn_dividendos.setEnabled(False)
        self.btn_taxa_aluguel.setEnabled(False)
        self.btn_resultados.setEnabled(False)

        class _AtualizarTudoThread(QThread):
            finished = Signal(dict)
            progress_etapa = Signal(int, str)
            progress_item = Signal(int, int, str)

            def __init__(self, db_path):
                super().__init__()
                self.db_path = db_path

            def run(self):
                resultado = {"status": "ok", "etapas": {}}

                # --- Etapa 1: ⚡ Importar ---
                self.progress_etapa.emit(1, "[1/4] Importando instrumentos...")
                try:
                    import sqlite3
                    from datetime import date
                    from dateutil.relativedelta import relativedelta
                    from collections import defaultdict
                    from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
                    from src.domain.entities.instrumento_opcional import TipoOpcao
                    from src.infrastructure.persistence.database import get_db_path

                    client = OpcoesNetClient()
                    ativos = client.fetch_available_assets()
                    if not ativos:
                        raise RuntimeError("Nao foi possivel obter lista de ativos")

                    real_db = str(get_db_path())
                    excluir_extra = ["IBOV11"]

                    import_max_months = 9
                    try:
                        conn_cfg = sqlite3.connect(real_db)
                        row_black = conn_cfg.execute(
                            "SELECT valor FROM parametros_operacionais WHERE chave = 'black_list_import'"
                        ).fetchone()
                        row_meses = conn_cfg.execute(
                            "SELECT valor FROM parametros_operacionais WHERE chave = 'import_max_months'"
                        ).fetchone()
                        conn_cfg.close()
                        if row_black and row_black[0]:
                            black_ativos = [a.strip().upper() for a in str(row_black[0]).split(",") if a.strip()]
                            for a in black_ativos:
                                if a not in excluir_extra:
                                    excluir_extra.append(a)
                        if row_meses and row_meses[0]:
                            try:
                                import_max_months = int(float(row_meses[0]))
                            except (ValueError, TypeError):
                                pass
                    except Exception:
                        pass

                    data_limite = date.today() + relativedelta(months=import_max_months)
                    todos_pares = []
                    total_ativos = len(ativos)

                    for idx, ativo in enumerate(ativos, 1):
                        if ativo.upper() in excluir_extra:
                            continue

                        self.progress_item.emit(idx, total_ativos, ativo)
                        try:
                            opcoes = client.fetch_all_options(ativo, delay=0.35)
                        except Exception:
                            continue

                        if not opcoes:
                            continue

                        opcoes_filtradas = [r for r in opcoes if r.get("vencimento", "") <= data_limite.isoformat()]
                        if not opcoes_filtradas:
                            continue

                        grupos = defaultdict(lambda: {"PUT": "", "CALL": "", "MOD": ""})
                        for r in opcoes_filtradas:
                            key = (r["ativo"], r["vencimento"], r["strike"])
                            if r["tipo"] == "PUT":
                                grupos[key]["PUT"] = r["ticker"]
                            else:
                                grupos[key]["CALL"] = r["ticker"]
                                if r.get("mod"):
                                    grupos[key]["MOD"] = r["mod"]

                        for (_ativo_key, ven, strike), p in grupos.items():
                            cod_put = p["PUT"]
                            cod_call = p["CALL"]
                            if not cod_put or not cod_call:
                                continue
                            mod = p.get("MOD", "")
                            if mod == "E":
                                tipo = TipoOpcao.EUROPEIA
                            elif mod == "A":
                                tipo = TipoOpcao.AMERICANA
                            else:
                                continue
                            todos_pares.append((_ativo_key, cod_put, cod_call, ven, strike, tipo.value))

                    if not todos_pares:
                        raise RuntimeError("Nenhum par encontrado")

                    conn = sqlite3.connect(real_db)
                    conn.execute("DELETE FROM instrumentos_base")
                    conn.commit()

                    inseridas = 0
                    for atv, cod_put, cod_call, ven, strike, tipo in todos_pares:
                        try:
                            conn.execute(
                                "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao, strike) VALUES (?, ?, ?, ?, ?, ?)",
                                (atv, cod_put, cod_call, ven, tipo, float(strike) if strike else None),
                            )
                            inseridas += 1
                        except sqlite3.IntegrityError:
                            pass

                    conn.commit()
                    conn.close()
                    resultado["etapas"]["importflash"] = {"ok": True}
                except Exception as e:
                    resultado["etapas"]["importflash"] = {"ok": False, "erro": str(e)}

                # --- Etapa 2: 📅 Proventos ---
                self.progress_etapa.emit(2, "[2/4] Coletando proventos...")
                try:
                    from src.infrastructure.providers.dividendos_statusinvest import DividendosStatusInvestProvider
                    from src.infrastructure.persistence.repositories.repositories import (
                        DividendoRepository,
                        InstrumentoRepository,
                    )

                    provider = DividendosStatusInvestProvider()
                    div_repo = DividendoRepository(self.db_path)
                    inst_repo = InstrumentoRepository(self.db_path)
                    instrumentos = inst_repo.get_all()
                    ativos = sorted(list(set(inst.ativo for inst in instrumentos)))

                    total_proventos = 0
                    total_ativos = len(ativos)
                    for i, ativo in enumerate(ativos):
                        self.progress_item.emit(i + 1, total_ativos, ativo)
                        dividendos = provider.buscar_proventos(ativo)
                        if dividendos:
                            div_repo.save_batch(dividendos)
                            total_proventos += len(dividendos)

                    resultado["etapas"]["proventos"] = {
                        "ok": True,
                        "proventos": total_proventos,
                        "ativos": total_ativos,
                    }
                except Exception as e:
                    resultado["etapas"]["proventos"] = {"ok": False, "erro": str(e)}

                # --- Etapa 3: 📊 Taxas de Aluguel ---
                self.progress_etapa.emit(3, "[3/4] Coletando taxas de aluguel...")
                try:
                    from src.application.use_cases.coletar_taxas_aluguel import ColetarTaxasAluguelUseCase
                    from src.infrastructure.persistence.repositories.repositories import ParametroRepository

                    param_repo = ParametroRepository(self.db_path)
                    hab = param_repo.get_by_chave("taxa_aluguel_habilitado")
                    if not hab or float(hab.valor) == 0.0:
                        resultado["etapas"]["taxas"] = {"ok": True, "pulado": "desabilitado"}
                    else:
                        use_case = ColetarTaxasAluguelUseCase(self.db_path)

                        def cb(corrente, total, ativo):
                            self.progress_item.emit(corrente, total, ativo)

                        resumo = use_case.executar(callback_progresso=cb)
                        resultado["etapas"]["taxas"] = {
                            "ok": resumo["status"] == "sucesso",
                            "sucessos": resumo["sucessos"],
                            "falhas": resumo["falhas"],
                        }
                except Exception as e:
                    resultado["etapas"]["taxas"] = {"ok": False, "erro": str(e)}

                # --- Etapa 4: 📅 Agenda de Resultados ---
                self.progress_etapa.emit(4, "[4/4] Coletando agenda de resultados...")
                try:
                    from src.infrastructure.providers.calendario_resultados_webwallet import CalendarioResultadosWebwalletProvider
                    from src.infrastructure.persistence.repositories.repositories import CalendarioResultadosRepository

                    crepo = CalendarioResultadosRepository(self.db_path)
                    web = CalendarioResultadosWebwalletProvider()

                    self.progress_item.emit(1, 4, "Webwallet (previstos)...")
                    previstos = web.buscar_todos()
                    crepo.delete_by_fonte("webwallet")
                    crepo.save_batch(previstos)

                    resultado["etapas"]["resultados"] = {
                        "ok": True,
                        "previstos": len(previstos),
                    }
                except Exception as e:
                    resultado["etapas"]["resultados"] = {"ok": False, "erro": str(e)}

                self.finished.emit(resultado)

        self._atualizar_tudo_started = False
        self._atualizar_tudo_progress_etapa = 0

        thread = _AtualizarTudoThread(self.db_path)
        verbos = {1: "Importando", 2: "Coletando", 3: "Coletando", 4: "Coletando"}

        thread.progress_etapa.connect(
            lambda etapa, msg: (
                setattr(self, "_atualizar_tudo_progress_etapa", etapa),
                self._status_left.setText(msg),
                self._status_left.setStyleSheet(
                    "color: {}; font-weight: bold;".format(
                        {1: Palette.ACCENT_BLUE_BRIGHT, 2: Palette.GREEN, 3: Palette.YELLOW, 4: Palette.ORANGE}.get(
                            etapa, Palette.ORANGE
                        )
                    )
                ),
            )[-1]
        )
        thread.progress_item.connect(
            lambda corr, tot, ativo: self._status_left.setText(
                f"[{ {1: '1', 2: '2', 3: '3', 4: '4'}.get(self._atualizar_tudo_progress_etapa, '?')}/4] "
                f"{verbos.get(self._atualizar_tudo_progress_etapa, 'Processando')} {ativo} ({corr}/{tot})..."
            )
        )
        thread.finished.connect(self._on_atualizar_tudo_finished)
        self._atualizar_tudo_thread = thread
        thread.start()

    def _on_atualizar_tudo_finished(self, resultado: dict):
        self.btn_atualizar_tudo.setEnabled(True)
        self.btn_atualizar_tudo.setText("\U0001f504  Atualizar")
        self.btn_importflash.setEnabled(True)
        self.btn_dividendos.setEnabled(True)
        self.btn_taxa_aluguel.setEnabled(True)
        self.btn_resultados.setEnabled(True)

        etapas = resultado.get("etapas", {})
        imp = etapas.get("importflash", {})
        prov = etapas.get("proventos", {})
        tax = etapas.get("taxas", {})
        res = etapas.get("resultados", {})

        imp_ok = imp.get("ok", False)
        prov_ok = prov.get("ok", False)
        tax_ok = tax.get("ok", False)

        linhas = []
        linhas.append(f"⚡ Importar: {'OK' if imp_ok else 'FALHA'}")
        if not imp_ok:
            linhas.append(f"   → {imp.get('erro', 'erro desconhecido')}")

        linhas.append(f"📅 Proventos: {'OK' if prov_ok else 'FALHA'}")
        if prov_ok:
            linhas.append(f"   → {prov.get('proventos', 0)} proventos em {prov.get('ativos', 0)} ativos")
        else:
            linhas.append(f"   → {prov.get('erro', 'erro desconhecido')}")

        linhas.append(f"📊 Taxas Aluguel: {'OK' if tax_ok else 'FALHA'}")
        if tax_ok:
            if "pulado" in tax:
                linhas.append(f"   → desabilitado nos parâmetros")
            else:
                linhas.append(f"   → {tax.get('sucessos', 0)} sucessos, {tax.get('falhas', 0)} falhas")
        else:
            linhas.append(f"   → {tax.get('erro', 'erro desconhecido')}")

        res_ok = res.get("ok", False)
        linhas.append(f"📅 Resultados: {'OK' if res_ok else 'FALHA'}")
        if res_ok:
            linhas.append(f"   → {res.get('previstos', 0)} previstos")
        else:
            linhas.append(f"   → {res.get('erro', 'erro desconhecido')}")

        msg = "\n".join(linhas)

        if imp_ok:
            self._worker.recarregar_instrumentos()

        self._status_left.setText("Atualização completa concluída!")
        self._status_left.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))

        QMessageBox.information(self, "Atualização Completa", msg)

        if prov_ok or tax_ok:
            self._abrir_visualizar_taxas()
