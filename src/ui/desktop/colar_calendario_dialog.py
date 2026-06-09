import logging
import winsound

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QLabel, QHeaderView, QLineEdit, QFormLayout, QFrame,
    QListWidget, QListWidgetItem, QWidget, QTextEdit, QSpinBox, QDoubleSpinBox,
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas
from src.ui.desktop.theme import Palette

CUSTOS_DISCLOSURE = (
    "\n\n* Custos já incluem taxa B3 (emolumento 0,025% + liquidação 0,0275% por perna) "
    "e IR (15% sobre o lucro líquido)."
)

logger = logging.getLogger(__name__)

WHITELIST_CHAVE = "white_list_colar_calendario"


def ler_whitelist_colar_calendario(db_path: str | None = None) -> list[str]:
    repo = ParametroRepository(db_path)
    param = repo.get_by_chave(WHITELIST_CHAVE)
    if param and param.valor:
        raw = str(param.valor)
        return [a.strip().upper() for a in raw.split(",") if a.strip()]
    return []


class ColarCalTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("% CDI", "pct_cdi"),
        ("PnL Bruto", "pnl_projetado"),
        ("PnL B3", "pnl_b3"),
        ("PnL Líq", "pnl_liquido"),
        ("Custo", "capital_empregado"),
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
        ("Viés", "tipo_str"),
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
            if role == Qt.ToolTipRole:
                tips = {
                    "ativo": "Código da ação objeto (ex: PETR4).",
                    "pct_cdi": "Retorno percentual comparado ao CDI do período." + CUSTOS_DISCLOSURE,
                    "pnl_projetado": "Resultado bruto projetado da estrutura no vencimento da CALL." + CUSTOS_DISCLOSURE,
                    "pnl_b3": "Resultado após custos B3 (emolumento + liquidação)." + CUSTOS_DISCLOSURE,
                    "pnl_liquido": "Resultado líquido final (B3 + IR deduzidos)." + CUSTOS_DISCLOSURE,
                    "capital_empregado": "Capital total empregado na montagem (ação + PUT − CALL).",
                    "vencimento_call": "Vencimento da CALL (perna curta, vence primeiro).",
                    "vencimento_put": "Vencimento da PUT (perna longa, vence depois).",
                    "strike_call": "Preço de exercício da CALL vendida.",
                    "strike_put": "Preço de exercício da PUT comprada.",
                    "cod_call": "Código da CALL na B3.",
                    "cod_put": "Código da PUT na B3.",
                    "iv_call": "Volatilidade implícita da CALL (Black-Scholes).",
                    "iv_put": "Volatilidade implícita da PUT (Black-Scholes).",
                    "premio_call": "Prêmio recebido pela venda da CALL.",
                    "premio_put": "Prêmio pago pela compra da PUT.",
                    "net_credito": "Crédito líquido recebido (CALL vendida − PUT comprada).",
                    "theta_call": "Decaimento temporal diário da CALL (Black-Scholes).",
                    "theta_put": "Decaimento temporal diário da PUT (Black-Scholes).",
                    "theta_liquido": "Theta líquido da estrutura (θ CALL − θ PUT). Positivo = ganha tempo.",
                    "valor_put_venc_call": "Valor estimado da PUT no vencimento da CALL, projetado pelo Black-Scholes.",
                    "tipo_str": "Classificação do viés: Alta, Baixa ou Neutro.",
                }
                return tips.get(self.COLUMNS[section][1])
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
                           "net_credito", "valor_put_venc_call", "pnl_projetado",
                           "pnl_b3", "pnl_liquido",
                           "capital_empregado"):
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
            if col_key in ("pnl_b3", "pnl_liquido"):
                val = item.get(col_key, 0)
                if val > 0:
                    return QBrush(QColor(Palette.GREEN))
                if val < 0:
                    return QBrush(QColor(Palette.RED))
                return QBrush(QColor(Palette.TEXT_MUTED))
            return QBrush(QColor(Palette.TEXT_MUTED))
        if role == Qt.TextAlignmentRole:
            center_cols = {"strike_call", "strike_put", "premio_call", "premio_put", "net_credito",
                           "iv_call", "iv_put", "theta_call", "theta_put", "theta_liquido",
                           "pct_cdi", "pnl_projetado", "pnl_b3", "pnl_liquido",
                           "tipo_str", "valor_put_venc_call",
                           "capital_empregado"}
            if col_key in center_cols:
                return Qt.AlignCenter | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.BackgroundRole:
            if not item.get("viavel", False):
                return QBrush(QColor(Palette.ROW_NOT_VIABLE))
            return None
        return None

    def atualizar(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()


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
    iniciar_scan_signal = pyqtSignal(list, dict)
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
        self._som_ativado = False
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
        self.btn_bell.toggled.connect(self._toggle_som)
        header_layout.addWidget(self.btn_bell)

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

        self.btn_regras = QPushButton("📋 Regras")
        self.btn_regras.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8b8be0;
                border: 1px solid #8b8be066; border-radius: 4px;
                padding: 4px; font-size: 8pt;
            }
            QPushButton:hover { background-color: #8b8be022; }
        """)
        self.btn_regras.clicked.connect(self._abrir_regras)
        left_panel.addWidget(self.btn_regras)

        self.lbl_scan_status = QLabel("✅ Pronto")
        self.lbl_scan_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 8pt;")
        left_panel.addWidget(self.lbl_scan_status)

        body_layout.addWidget(left_widget)

        self.table_view = QTableView()
        self.model = ColarCalTableModel()

        self.proxy = ColarCalSortProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.proxy.sort(1, Qt.DescendingOrder)

        self.table_view.setModel(self.proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 8))
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setDragEnabled(True)
        header.sectionMoved.connect(lambda: salvar_ordem_colunas(header, "colar_cal_table_order"))
        restaurar_ordem_colunas(header, "colar_cal_table_order")
        header.setSectionResizeMode(QHeaderView.Interactive)
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

    def _restart_scan_if_auto(self):
        if self._auto_mode:
            self.parar_scan_signal.emit()
            selecionados = [self.lista_ativos.item(i).text()
                            for i in range(1, self.lista_ativos.count())
                            if self.lista_ativos.item(i).checkState() == Qt.Checked]
            self.iniciar_scan_signal.emit(selecionados, {})

    def _on_asset_check_changed(self, item):
        self._aplicar_filtro_lista()
        self._restart_scan_if_auto()

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
        self._restart_scan_if_auto()

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
        self.btn_scan.setEnabled(n_sel > 0 and not self._scanning)
        self.selecao_alterada.emit(selecionados if not todos_marcados else [])
        self._atualizar_status()

    def _atualizar_status(self):
        total = self.proxy.rowCount()
        filtro = self.txt_filtro.text().strip()
        has_results = getattr(self, "_dados_carregados", False)
        if total == 0 and filtro:
            self.lbl_status.setText(f"Nenhum colar para '{filtro}'")
        elif total == 0:
            if has_results:
                self.lbl_status.setText("Nenhum colar viável para a seleção")
            else:
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
            if n_sel > 20:
                from PyQt5.QtWidgets import QMessageBox
                resp = QMessageBox.question(
                    self, "Muitos ativos",
                    f"{n_sel} ativos selecionados.\n"
                    "A varredura pode levar vários minutos até todos\n"
                    "os instrumentos terem dados RTD completos.\n\n"
                    "Deseja continuar mesmo assim?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if resp != QMessageBox.Yes:
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
            self.iniciar_scan_signal.emit(selecionados, {})

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

        def add_row(nome, valor, cor=None, tooltip=None):
            lbl = QLabel(nome)
            lbl.setStyleSheet(label_style)
            val = QLabel(valor)
            if tooltip:
                val.setToolTip(tooltip)
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

        add_row("Crédito Líquido:", f"R$ {r.net_credito:.2f}", cor=Palette.YELLOW,
                tooltip="Prêmio recebido pela CALL menos prêmio pago pela PUT, já descontados custos." + CUSTOS_DISCLOSURE)
        add_row("Theta Líquido:", f"{r.theta_liquido:.3f} por dia",
                cor=Palette.GREEN if r.theta_liquido > 0 else Palette.RED,
                tooltip="Decaimento temporal líquido por dia. Positivo = o tempo corre a seu favor." + CUSTOS_DISCLOSURE)
        add_row("Valor Put no VC Call:", f"R$ {r.valor_put_venc_call:.2f}", cor=Palette.CYAN,
                tooltip="Valor da PUT no vencimento da CALL, projetado pelo modelo Black-Scholes.")
        add_row("Custo Montagem:", f"R$ {r.capital_empregado:.2f}",
                tooltip="Capital total empregado na operação (ação + prêmios líquidos)." + CUSTOS_DISCLOSURE)
        pnl_b3 = r.pnl_projetado - r.custo_b3
        pnl_liquido = pnl_b3 - r.custo_ir
        add_row("PnL Bruto:", f"R$ {r.pnl_projetado:.2f}",
                tooltip="Lucro/prejuízo bruto no vencimento da CALL (sem custos)." + CUSTOS_DISCLOSURE)
        add_row("− Custos B3:", f"−R$ {r.custo_b3:.2f}",
                cor=Palette.ORANGE,
                tooltip="Emolumento + liquidação + registro + ISS." + CUSTOS_DISCLOSURE)
        add_row("= PnL pós-B3:", f"R$ {pnl_b3:.2f}",
                cor=Palette.GREEN if pnl_b3 > 0 else Palette.RED,
                tooltip="Lucro/prejuízo após deduzir taxas B3." + CUSTOS_DISCLOSURE)
        if r.custo_ir > 0:
            add_row("− IR (15%):", f"−R$ {r.custo_ir:.2f}",
                    cor=Palette.ORANGE,
                    tooltip="Imposto de Renda (15% sobre lucro líquido pós-B3)." + CUSTOS_DISCLOSURE)
        add_row("= PnL Líquido:", f"R$ {pnl_liquido:.2f} ({r.pct_retorno:.2f}%)",
                cor=Palette.GREEN if pnl_liquido > 0 else Palette.RED,
                tooltip="Lucro/prejuízo líquido final (B3 + IR deduzidos)." + CUSTOS_DISCLOSURE)
        add_row("% CDI Líq:", f"{r.pct_cdi_liquido:.2f}x",
                cor=Palette.GREEN if r.pct_cdi_liquido >= 1.0 else Palette.RED,
                tooltip="Retorno líquido (pós-B3 e IR) comparado ao CDI do período." + CUSTOS_DISCLOSURE)
        if r.be_baixa is not None:
            add_row("BE Baixa (B&S):", f"R$ {r.be_baixa:.2f}", cor=Palette.CYAN)
        if r.be_alta is not None:
            add_row("BE Alta (B&S):", f"R$ {r.be_alta:.2f}", cor=Palette.CYAN)
        if r.be_baixa_intrinseco is not None:
            add_row("BE Baixa (Intrínseco):", f"R$ {r.be_baixa_intrinseco:.2f}", cor=Palette.GREEN)
        if r.be_alta_intrinseco is not None:
            add_row("BE Alta (Intrínseco):", f"R$ {r.be_alta_intrinseco:.2f}", cor=Palette.RED)

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

        btn_variacao = QPushButton("📈 Ver Variação")
        btn_variacao.setAutoDefault(False)
        btn_variacao.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_variacao.clicked.connect(lambda: self._mostrar_variacao(r))
        btn_row.addWidget(btn_variacao)

        btn_explicar = QPushButton("🔍 Explicar")
        btn_explicar.setAutoDefault(False)
        btn_explicar.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_explicar.clicked.connect(lambda: self._explicar_estrategia(r))
        btn_row.addWidget(btn_explicar)

        btn_export = QPushButton("📋 Exportar Debug")
        btn_export.setAutoDefault(False)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_export.clicked.connect(lambda: self._exportar_debug(r))
        btn_row.addWidget(btn_export)
        btn_row.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)

        layout.addLayout(btn_row)
        dialog.exec_()

    def _exportar_debug(self, r):
        from PyQt5.QtWidgets import QApplication, QMessageBox
        import numpy as np
        from scipy.stats import norm

        T_call = r.dte_call / 365
        T_put = r.dte_put / 365
        T_rem = r.dte_extra / 365
        du = round(r.dte_call * 252 / 365)
        repo = ParametroRepository(self._db_path)
        param = repo.get_by_chave("taxa_cdi")
        rf = param.valor if param else 0.1450
        cdi_periodo = (1 + rf) ** (du / 252) - 1
        pnl_stk = min(r.preco_ativo, r.strike_call) - r.preco_ativo
        pnl_call = r.premio_call
        if T_rem > 0:
            dp1 = (np.log(r.preco_ativo / r.strike_put) + (rf + 0.5 * (r.iv_put / 100) ** 2) * T_rem) / ((r.iv_put / 100) * np.sqrt(T_rem))
            dp2 = dp1 - (r.iv_put / 100) * np.sqrt(T_rem)
            put_val_vc = r.strike_put * np.exp(-rf * T_rem) * norm.cdf(-dp2) - r.preco_ativo * norm.cdf(-dp1)
        else:
            put_val_vc = max(r.strike_put - r.preco_ativo, 0)

        pnl_put = put_val_vc - r.premio_put
        pnl_total = pnl_stk + pnl_call + pnl_put
        cap = r.capital_empregado
        ret = pnl_total / cap if cap > 0 else 0
        pct_cdi = ret / cdi_periodo if cdi_periodo > 0 else 0

        lines = [
            "=== DEBUG COLLAR CALENDARIO ===",
            "",
            "--- INPUTS ---",
            f"Ativo:          {r.ativo}",
            f"Spot:           R$ {r.preco_ativo:.4f}",
            f"Cod Call:       {r.cod_call}",
            f"Strike Call:    R$ {r.strike_call:.4f}  (RTD PEX)",
            f"Cod Put:        {r.cod_put}",
            f"Strike Put:     R$ {r.strike_put:.4f}  (RTD PEX)",
            f"Premio Call:    R$ {r.premio_call:.4f}  (OCP)",
            f"Premio Put:     R$ {r.premio_put:.4f}  (OVD)",
            f"DTE Call:       {r.dte_call}d",
            f"DTE Put:        {r.dte_put}d",
            f"DTE Extra:      {r.dte_extra}d",
            f"IV Call:        {r.iv_call:.2f}%",
            f"IV Put:         {r.iv_put:.2f}%",
            f"Venc Call:      {r.vencimento_call}",
            f"Venc Put:       {r.vencimento_put}",
            "",
            "--- MODELO COBERTO (acao + opcoes) ---",
            f"T_call (anos):  {T_call:.6f}",
            f"T_rem  (anos):  {T_rem:.6f}",
            f"r (fixa):       {rf:.4f}",
            f"CDI periodo:    {cdi_periodo*100:.4f}% = (1+{rf})^({du}/252)-1",
            f"Acao comprada a R$ {r.preco_ativo:.2f}",
            f"Acao PnL:      min({r.preco_ativo:.2f}, {r.strike_call:.2f}) - {r.preco_ativo:.2f} = R$ {pnl_stk:.4f}",
            f"Short Call PnL: R$ {r.premio_call:.4f} (premio recebido, acao cobre)",
            f"Put val @callVC: BS(S={r.preco_ativo:.2f}, K={r.strike_put:.2f}, T={T_rem:.4f}, r={rf:.4f}, IV={r.iv_put:.2f}%) = R$ {put_val_vc:.4f}",
            f"Long Put PnL:   {put_val_vc:.4f} - {r.premio_put:.4f} = R$ {pnl_put:.4f}",
            f"Capital empreg: R$ {cap:.4f}",
            "",
            "--- RESULTADO ---",
            f"PnL Projetado:  R$ {pnl_total:.4f}",
            f"pct_retorno:    {ret*100:.2f}% = {pnl_total:.4f}/{cap:.4f}",
            f"pct_cdi:        {pct_cdi:.2f}x = {ret*100:.2f}% / {cdi_periodo*100:.4f}%",
            f"Net Credito:    R$ {r.net_credito:.4f}",
            f"Valor Put VC:   R$ {r.valor_put_venc_call:.4f}",
            f"Tipo:           {r.tipo.value}",
            f"Viavel:         {r.viavel}",
        ]
        be_baixa_bs = f"BE Baixa B&S:   R$ {r.be_baixa:.2f}" if r.be_baixa is not None else "BE Baixa B&S:   N/D"
        be_alta_bs = f"BE Alta B&S:    R$ {r.be_alta:.2f}" if r.be_alta is not None else "BE Alta B&S:    N/D"
        be_baixa_int = f"BE Baixa Intr:  R$ {r.be_baixa_intrinseco:.2f}" if r.be_baixa_intrinseco is not None else "BE Baixa Intr:  N/D"
        be_alta_int = f"BE Alta Intr:   R$ {r.be_alta_intrinseco:.2f}" if r.be_alta_intrinseco is not None else "BE Alta Intr:   N/D"
        lines.extend(["", "--- BREAKEVENS ---", be_baixa_bs, be_alta_bs, be_baixa_int, be_alta_int])
        texto = "\n".join(lines)
        QApplication.clipboard().setText(texto)
        QMessageBox.information(self, "Debug Exportado",
                                "Dados de debug copiados para a área de transferência.\n"
                                "Cole (Ctrl+V) aqui no chat.")

    def _explicar_estrategia(self, r):
        from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario

        html = CalculadoraColarCalendario.gerar_explicacao(r)
        dialog = QDialog(self, Qt.Window)
        dialog.setWindowTitle(f"Explicação — Collar Calendário {r.ativo}")
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        texto = QTextEdit()
        texto.setReadOnly(True)
        texto.setHtml(html)
        texto.setStyleSheet(f"""
            QTextEdit {{
                background-color: #15152a;
                color: #e0e0e0;
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                font-size: 10pt;
                padding: 12px;
            }}
        """)
        layout.addWidget(texto, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(dialog.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _plot_payoff(self, r):
        from PyQt5.QtWidgets import QMessageBox
        import traceback
        try:
            import numpy as np
            from scipy.stats import norm
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure

            S0 = r.preco_ativo
            Kc = r.strike_call
            Kp = r.strike_put
            Pc = r.premio_call
            Pp = r.premio_put
            iv_c = r.iv_call / 100
            iv_p = r.iv_put / 100
            T_call = r.dte_call / 365
            T_rem = r.dte_extra / 365

            x_min = min(Kp, S0) * 0.85
            x_max = max(Kc, S0) * 1.15
            x = np.linspace(x_min, x_max, 500)

            repo = ParametroRepository(self._db_path)
            param = repo.get_by_chave("taxa_cdi")
            rf = param.valor if param else 0.1450
            stock_pnl = np.minimum(x, Kc) - S0  # acao vendida a Kc se ITM
            call_pnl = Pc  # premio recebido, acao cobre exercicio
            if T_rem > 0:
                dp1 = (np.log(x / Kp) + (rf + 0.5 * iv_p ** 2) * T_rem) / (iv_p * np.sqrt(T_rem))
                dp2 = dp1 - iv_p * np.sqrt(T_rem)
                put_val = Kp * np.exp(-rf * T_rem) * norm.cdf(-dp2) - x * norm.cdf(-dp1)
            else:
                put_val = np.maximum(Kp - x, 0)
            put_pnl = put_val - Pp

            pnl = stock_pnl + call_pnl + put_pnl

            # Sigmas (1 desvio = S0 * IV_call * sqrt(T_call))
            sigma_spot = S0 * iv_c * np.sqrt(T_call)

            BG = '#0d0d0d'; TEXT = '#c0c0c0'; RED = '#ff3355'
            ACCENT = '#ffc107'; FILL_BLUE = '#1a5276'; SIGMA_C = '#6c5ce7'

            fig = Figure(figsize=(8, 4.5), facecolor=BG)
            ax = fig.add_subplot(111, facecolor=BG)

            ax.plot(x, pnl, color=ACCENT, linewidth=2.0, label='Payoff')

            hover_annot = ax.annotate(
                '', xy=(0, 0), fontsize=8, color='#fff',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=ACCENT, alpha=0.9),
                ha='center', va='bottom', visible=False,
            )
            def _on_hover(event):
                if event.inaxes != ax or event.xdata is None:
                    hover_annot.set_visible(False)
                    fig.canvas.draw_idle()
                    return
                idx = np.argmin(np.abs(x - event.xdata))
                xv, yv = x[idx], pnl[idx]
                hover_annot.xy = (xv, yv)
                hover_annot.set_text(f'R$ {xv:.2f} → R$ {yv:+.2f}')
                hover_annot.set_visible(True)
                fig.canvas.draw_idle()
            ax.axhline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.3)
            ax.axvline(S0, color='#2196f3', linewidth=0.7, linestyle='--', alpha=0.8, label=f'Entrada {S0:.2f}')
            ax.axvline(Kp, color=RED, linewidth=0.7, linestyle='--', alpha=0.8, label=f'K Put {Kp:.2f}')
            ax.axvline(Kc, color=ACCENT, linewidth=0.7, linestyle='--', alpha=0.8, label=f'K Call {Kc:.2f}')

            for n in [-2, -1, 1, 2]:
                px = S0 + n * sigma_spot
                if x_min <= px <= x_max:
                    ax.axvline(px, color=SIGMA_C, linewidth=0.5, linestyle=':', alpha=0.5)
                    ax.text(px, ax.get_ylim()[0], f'{n:+d}σ\n{px:.2f}',
                            color=SIGMA_C, fontsize=6, ha='center', va='bottom')

            # Breakevens
            be_color_bs = '#6c5ce7'
            be_color_int = '#fd79a8'
            ylim_bottom, ylim_top = ax.get_ylim()
            y_bs = ylim_top * 0.05
            y_int = ylim_top * 0.14
            if r.be_baixa is not None:
                ax.axvline(r.be_baixa, color=be_color_bs, linewidth=1.2, linestyle='--', alpha=0.9)
                dx_bs = (r.be_alta - r.be_baixa) * 0.02 if r.be_alta is not None else 0
                ax.annotate(f'BE B&S {r.be_baixa:.2f}', xy=(r.be_baixa, 0),
                            xytext=(r.be_baixa - dx_bs, y_bs),
                            color=be_color_bs, fontsize=7, ha='center',
                            arrowprops=dict(arrowstyle='->', color=be_color_bs, lw=0.8))
            if r.be_alta is not None:
                ax.axvline(r.be_alta, color=be_color_bs, linewidth=1.2, linestyle='--', alpha=0.9,
                           label='BE B&S')
                dx_bs = (r.be_alta - r.be_baixa) * 0.02 if r.be_baixa is not None else 0
                ax.annotate(f'BE B&S {r.be_alta:.2f}', xy=(r.be_alta, 0),
                            xytext=(r.be_alta + dx_bs, y_bs),
                            color=be_color_bs, fontsize=7, ha='center',
                            arrowprops=dict(arrowstyle='->', color=be_color_bs, lw=0.8))
            if r.be_baixa_intrinseco is not None:
                ax.axvline(r.be_baixa_intrinseco, color=be_color_int, linewidth=1.2, linestyle=':', alpha=0.9)
                dx_int = (r.be_alta_intrinseco - r.be_baixa_intrinseco) * 0.02 if r.be_alta_intrinseco is not None else 0
                ax.annotate(f'BE Intr {r.be_baixa_intrinseco:.2f}', xy=(r.be_baixa_intrinseco, 0),
                            xytext=(r.be_baixa_intrinseco - dx_int, y_int),
                            color=be_color_int, fontsize=7, ha='center',
                            arrowprops=dict(arrowstyle='->', color=be_color_int, lw=0.8))
            if r.be_alta_intrinseco is not None:
                ax.axvline(r.be_alta_intrinseco, color=be_color_int, linewidth=1.2, linestyle=':', alpha=0.9,
                           label='BE Intrínseco')
                dx_int = (r.be_alta_intrinseco - r.be_baixa_intrinseco) * 0.02 if r.be_baixa_intrinseco is not None else 0
                ax.annotate(f'BE Intr {r.be_alta_intrinseco:.2f}', xy=(r.be_alta_intrinseco, 0),
                            xytext=(r.be_alta_intrinseco + dx_int, y_int),
                            color=be_color_int, fontsize=7, ha='center',
                            arrowprops=dict(arrowstyle='->', color=be_color_int, lw=0.8))

            ax.fill_between(x, 0, pnl, where=(pnl >= 0), color=FILL_BLUE, alpha=0.12)
            ax.fill_between(x, 0, pnl, where=(pnl < 0), color=RED, alpha=0.1)

            ax.set_xlabel('Preço do Ativo no Vencimento da Call (R$)', color=TEXT, fontsize=9)
            ax.set_ylabel('Lucro / Prejuízo (R$)', color=TEXT, fontsize=9)
            ax.set_title(f'Payoff Collar Calendário (Coberto) — {r.ativo}', color='#e0e0e0', fontsize=11, fontweight='bold')

            ax.tick_params(colors=TEXT, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color('#333')
            leg = ax.legend(loc='best', fontsize=7, labelcolor=TEXT, facecolor='#1a1a1a', edgecolor='#333')

            fig.tight_layout()

            payoff_dialog = QDialog(self, Qt.Window)
            payoff_dialog.setWindowTitle(f"Payoff Calendário — {r.ativo}")
            payoff_dialog.setMinimumSize(800, 500)
            payoff_layout = QVBoxLayout(payoff_dialog)
            payoff_layout.setContentsMargins(8, 8, 8, 8)
            canvas = FigureCanvas(fig)
            fig.canvas.mpl_connect('motion_notify_event', _on_hover)
            payoff_layout.addWidget(canvas)

            be_parts = []
            if r.be_baixa is not None and r.be_alta is not None:
                be_parts.append(f"BE B&S: R$ {r.be_baixa:.2f} — R$ {r.be_alta:.2f}")
            elif r.be_baixa is not None:
                be_parts.append(f"BE Baixa B&S: R$ {r.be_baixa:.2f}")
            elif r.be_alta is not None:
                be_parts.append(f"BE Alta B&S: R$ {r.be_alta:.2f}")
            if r.be_baixa_intrinseco is not None and r.be_alta_intrinseco is not None:
                be_parts.append(f"BE Intr: R$ {r.be_baixa_intrinseco:.2f} — R$ {r.be_alta_intrinseco:.2f}")
            elif r.be_baixa_intrinseco is not None:
                be_parts.append(f"BE Baixa Intr: R$ {r.be_baixa_intrinseco:.2f}")
            elif r.be_alta_intrinseco is not None:
                be_parts.append(f"BE Alta Intr: R$ {r.be_alta_intrinseco:.2f}")
            be_str = "  |  " + "  |  ".join(be_parts) if be_parts else ""

            footer = QLabel(
                f"{r.ativo}  |  "
                f"Spot: R$ {S0:.2f}  |  "
                f"Call {r.cod_call} K={Kc:.2f}: +R$ {Pc:.2f}  |  "
                f"Put {r.cod_put} K={Kp:.2f}: −R$ {Pp:.2f}  |  "
                f"Capital: R$ {S0 + Pp - Pc:.2f}  |  "
                f"PnL Proj: R$ {r.pnl_projetado:.2f} ({r.pct_retorno:.2f}% / {r.pct_cdi:.2f}x CDI)"
                f"{be_str}"
            )
            footer.setStyleSheet(f"""
                QLabel {{
                    color: {Palette.TEXT_SECONDARY};
                    font-size: 8pt;
                    font-family: Consolas;
                    padding: 4px 0;
                }}
            """)
            payoff_layout.addWidget(footer)

            btn_close = QPushButton("Fechar")
            btn_close.setAutoDefault(False)
            btn_close.clicked.connect(payoff_dialog.close)
            payoff_layout.addWidget(btn_close, alignment=Qt.AlignRight)
            payoff_dialog.exec_()
        except Exception as e:
            logger.exception("Erro no payoff: %s", e)
            QMessageBox.critical(self, "Erro", f"Falha ao gerar payoff:\n{e}\n\n{traceback.format_exc()}")

    def _mostrar_variacao(self, r, n_sessoes=None):
        from PyQt5.QtWidgets import QMessageBox
        from datetime import date, timedelta
        import re as re2
        import numpy as np
        from scipy.stats import norm
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import traceback

        if n_sessoes is None:
            n_sessoes = max(5, r.dte_call)

        try:
            client = OpcoesNetClient()
            hoje = date.today()
            raw = client.get_variacao(
                r.ativo,
                data_inicial=(hoje - timedelta(days=365)).strftime("%d/%m/%Y"),
                data_final=hoje.strftime("%d/%m/%Y"),
            )

            if not raw:
                QMessageBox.information(
                    self, "Variação",
                    f"Não foi possível obter dados de variação para {r.ativo}.\n"
                    "Verifique se o .env tem CPF/senha válidos do opcoes.net.br."
                )
                return

            dados = raw.get("data", {})
            chave_alvo = None
            for k in dados:
                if str(n_sessoes) in k:
                    chave_alvo = k
                    break
            if not chave_alvo:
                max_n = 0
                for k in dados:
                    nums = re2.findall(r'\d+', k)
                    if nums:
                        n = int(nums[-1])
                        if n > max_n:
                            max_n = n
                            chave_alvo = k
                if not chave_alvo:
                    chave_alvo = list(dados.keys())[0]
            bins = dados[chave_alvo]
            total_obs = sum(b["quantidade"] for b in bins)
            dias_neg = raw.get("diasComNegociacao", 0)

            CLASS_KEY = "classifica\u00e7\u00e3o"
            cents, wts = [], []
            for b in bins:
                q = b["quantidade"]
                if q <= 0:
                    continue
                rot = b[CLASS_KEY]
                nums = [float(x.replace(",", ".")) for x in re2.findall(r'[\d,.]+', rot)]
                if "Menos" in rot:
                    c = nums[0] / 2
                elif "Mais" in rot:
                    c = nums[0] * 1.5
                elif len(nums) >= 2:
                    c = (nums[0] + nums[1]) / 2
                else:
                    c = nums[0]
                cents.append(c)
                wts.append(q)

            media = sum(c * w for c, w in zip(cents, wts)) / sum(wts) if wts else 0
            desvio = (sum(w * (c - media) ** 2 for c, w in zip(cents, wts)) / sum(wts)) ** 0.5 if wts else 0

            pct_call = ((r.strike_call - r.preco_ativo) / r.preco_ativo) * 100
            pct_put = ((r.strike_put - r.preco_ativo) / r.preco_ativo) * 100

            spot = r.preco_ativo

            def preco_no_sigma(n_sigma):
                return spot * (1 + n_sigma * desvio / 100)

            BG = '#0d0d0d'; TEXT = '#c0c0c0'; ACCENT = '#ffc107'
            BLUE = '#2196f3'; GREEN = '#4caf50'; RED = '#ff3355'; PURPLE = '#9c27b0'

            fig = Figure(figsize=(11, 5.5), facecolor=BG)
            ax1 = fig.add_subplot(121, facecolor=BG)
            rotulos = [b[CLASS_KEY] for b in bins]
            vals = [b["percentual"] for b in bins]
            cores_b = [BLUE, GREEN, ACCENT, RED][:len(vals)]
            ax1.bar(range(len(vals)), vals, color=cores_b, alpha=0.7, width=0.6, edgecolor='#333', linewidth=0.5)
            for i, v in enumerate(vals):
                ax1.text(i, v + 0.5, f"{v:.1f}%", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
            ax1.set_xticks(range(len(vals)))
            ax1.set_xticklabels(rotulos, color=TEXT, fontsize=7)
            ax1.set_ylabel("% das observacoes", color=TEXT, fontsize=9)
            ax1.set_title(f"{r.ativo} - Variacao em ~{n_sessoes} pregoes\n{dias_neg} dias de amostra",
                          color='#e0e0e0', fontsize=10, fontweight='bold')
            ax1.set_facecolor(BG)
            ax1.tick_params(colors=TEXT, labelsize=8)
            ax1.set_ylim(0, max(vals) * 1.25)
            for s in ax1.spines.values():
                s.set_color('#333')
            info_hist = (f"Spot: R$ {spot:.2f}\n"
                         f"K Call: R$ {r.strike_call:.2f}\n"
                         f"K Put:  R$ {r.strike_put:.2f}")
            ax1.text(0.98, 0.98, info_hist, transform=ax1.transAxes, fontsize=7,
                     verticalalignment='top', horizontalalignment='right', color=TEXT,
                     bbox=dict(boxstyle='round', facecolor='#1a1a1a', edgecolor='#333'))

            ax2 = fig.add_subplot(122, facecolor=BG)
            x_lim = max(desvio * 4, 12)
            x = np.linspace(-x_lim, x_lim, 800)
            y = norm.pdf(x, 0, desvio) if desvio > 0 else np.zeros_like(x)
            y_max = max(y) * 1.45

            ax2.plot(x, y, color=ACCENT, linewidth=2.5, label='Dist. Normal')
            ax2.set_facecolor(BG)
            ax2.set_xlim(-x_lim, x_lim)
            ax2.set_ylim(-y_max * 0.3, y_max)

            ax2.fill_between(x, 0, y, where=(x >= -desvio) & (x <= desvio),
                             color=BLUE, alpha=0.12)
            ax2.fill_between(x, 0, y, where=(x >= desvio) & (x <= 2 * desvio),
                             color=GREEN, alpha=0.07)
            ax2.fill_between(x, 0, y, where=(x >= -2 * desvio) & (x <= -desvio),
                             color=GREEN, alpha=0.07)
            ax2.fill_between(x, 0, y, where=(x >= 2 * desvio) & (x <= 3 * desvio),
                             color=RED, alpha=0.04)
            ax2.fill_between(x, 0, y, where=(x >= -3 * desvio) & (x <= -2 * desvio),
                             color=RED, alpha=0.04)

            ax2.text(0, y_max * 0.88, "68%", ha='center', va='center', color=BLUE,
                     fontsize=12, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=BLUE, alpha=0.9))
            ax2.text(1.5 * desvio, y_max * 0.62, "13.5%", ha='center', va='center',
                     color=GREEN, fontsize=8)
            ax2.text(-1.5 * desvio, y_max * 0.62, "13.5%", ha='center', va='center',
                     color=GREEN, fontsize=8)
            ax2.text(2.5 * desvio, y_max * 0.35, "2.35%", ha='center', va='center',
                     color=RED, fontsize=7)
            ax2.text(-2.5 * desvio, y_max * 0.35, "2.35%", ha='center', va='center',
                     color=RED, fontsize=7)

            ax2.axvline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.2)
            for i in range(1, 4):
                cor = [BLUE, GREEN, RED][i - 1]
                ax2.axvline(i * desvio, color=cor, linewidth=0.6, linestyle='--', alpha=0.3)
                ax2.axvline(-i * desvio, color=cor, linewidth=0.6, linestyle='--', alpha=0.3)

            eixo_y_seta = -y_max * 0.08
            eixo_y_texto = -y_max * 0.15
            for i in range(-3, 4):
                variacao_pct = i * desvio
                cor = ACCENT if i == 0 else ([BLUE, GREEN, RED][abs(i) - 1] if abs(i) <= 3 else TEXT)
                preco_r = preco_no_sigma(i)
                ax2.annotate('', xy=(variacao_pct, 0), xytext=(variacao_pct, eixo_y_seta),
                             arrowprops=dict(arrowstyle='->', color=cor, lw=1.5, alpha=0.8))
                texto_preco = f"R${preco_r:.2f}"
                if i == 0:
                    texto_preco += " (spot)"
                ax2.text(variacao_pct, eixo_y_texto, texto_preco, ha='center', va='top',
                         color=cor, fontsize=7.5, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.2', facecolor='#1a1a1a',
                                   edgecolor=cor, alpha=0.8))
                sigma_label = f"{i:+d}s" if i != 0 else "0"
                ax2.text(variacao_pct, eixo_y_seta - y_max * 0.04, sigma_label,
                         ha='center', va='top', color=TEXT, fontsize=6.5, alpha=0.6)

            # Linha vertical do spot (variação 0%)
            ax2.axvline(0, color='#2196f3', linewidth=1.2, linestyle='--', alpha=0.7,
                        label=f'Spot R${spot:.2f} (0%)')

            if abs(pct_call - pct_put) < 0.1:
                pct_k = (pct_call + pct_put) / 2
                z_k = abs(pct_k) / desvio if desvio > 0 else 0
                percentil = norm.cdf(z_k) * 100
                ax2.axvline(pct_k, color=PURPLE, linewidth=2.5, linestyle='-', alpha=0.95,
                            label=f'K R${r.strike_call:.2f} (Z={z_k:.2f})')
                ax2.axvspan(pct_k - 0.5, pct_k + 0.5, color=PURPLE, alpha=0.08)
                ax2.text(pct_k, y_max * 0.50, f"Strike no\npercentil {percentil:.0f}%",
                         ha='center', va='center', color=PURPLE, fontsize=7.5, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a',
                                   edgecolor=PURPLE, alpha=0.85))
            else:
                ax2.axvline(pct_call, color=RED, linewidth=2, linestyle='-', alpha=0.9,
                            label=f'K Call {r.strike_call:.2f} ({pct_call:+.1f}%)')
                ax2.axvline(pct_put, color=GREEN, linewidth=2, linestyle='-', alpha=0.9,
                            label=f'K Put {r.strike_put:.2f} ({pct_put:+.1f}%)')

            ax2.axhline(0, color=TEXT, linewidth=0.4, alpha=0.15)
            ax2.set_xlabel('Variacao em relacao ao spot (%)', color=TEXT, fontsize=9)
            ax2.set_ylabel('Densidade', color=TEXT, fontsize=9)
            ax2.set_title("Dist. Normal - Probabilidades e Precos Correspondentes",
                          color='#e0e0e0', fontsize=10, fontweight='bold')
            ax2.tick_params(colors=TEXT, labelsize=8)
            for s in ax2.spines.values():
                s.set_color('#333')

            leg = ax2.legend(loc='upper right', fontsize=7, labelcolor=TEXT,
                             facecolor='#1a1a1a', edgecolor='#333')
            leg.get_frame().set_alpha(0.95)

            texto_info = (f"Media: {media:.1f}%\n"
                          f"Desvio: {desvio:.1f}%\n"
                          f"Obs: {total_obs}")
            ax2.text(0.02, 0.98, texto_info, transform=ax2.transAxes, fontsize=7,
                     verticalalignment='top', color=TEXT,
                     bbox=dict(boxstyle='round', facecolor='#1a1a1a', edgecolor='#333'))

            fig.tight_layout()

            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit

            input_style = """
                QLineEdit {
                    background-color: #1e1e2f; color: #e0e0e0;
                    border: 1px solid #2d2d44; border-radius: 4px;
                    padding: 4px 8px; font-size: 9pt;
                }
                QLineEdit:focus { border-color: #1abc9c; }
            """

            dialog = QDialog(self, Qt.Window)
            dialog.setWindowTitle(f"Variacao Historica - {r.ativo}")
            dialog.setMinimumSize(1050, 580)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            title = QLabel(
                f"<b>{r.ativo}</b>  |  "
                f"Spot: R$ {spot:.2f}  |  "
                f"K: R$ {r.strike_call:.2f} / R$ {r.strike_put:.2f}"
            )
            title.setStyleSheet(f"font-size: 10pt; color: {Palette.TEXT_PRIMARY};")
            layout.addWidget(title)

            control_row = QHBoxLayout()
            control_row.setSpacing(8)
            lbl_periodo = QLabel("Período (pregões):")
            lbl_periodo.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;")
            inp_periodo = QLineEdit(str(n_sessoes))
            inp_periodo.setFixedWidth(60)
            inp_periodo.setStyleSheet(input_style)
            btn_atualizar = QPushButton("Atualizar")
            btn_atualizar.setAutoDefault(False)
            btn_atualizar.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                    border: 1px solid {Palette.BORDER}; border-radius: 4px;
                    padding: 4px 14px; font-size: 9pt;
                }}
                QPushButton:hover {{ background-color: #3d3d55; }}
            """)
            def _reload():
                try:
                    novo_n = int(inp_periodo.text().strip())
                    if novo_n >= 5:
                        dialog.accept()
                        self._mostrar_variacao(r, novo_n)
                except ValueError:
                    pass
            btn_atualizar.clicked.connect(_reload)
            control_row.addWidget(lbl_periodo)
            control_row.addWidget(inp_periodo)
            control_row.addWidget(btn_atualizar)
            control_row.addStretch()
            layout.addLayout(control_row)

            canvas = FigureCanvas(fig)
            layout.addWidget(canvas, stretch=1)

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            btn_fechar = QPushButton("Fechar")
            btn_fechar.setAutoDefault(False)
            btn_fechar.clicked.connect(dialog.close)
            btn_fechar.setProperty("class", "primary")
            btn_row.addWidget(btn_fechar)
            layout.addLayout(btn_row)

            dialog.exec_()
        except Exception as e:
            logger.exception("Erro ao exibir variacao: %s", e)
            QMessageBox.critical(self, "Erro", f"Falha ao carregar variação:\n{e}\n\n{traceback.format_exc()}")

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
        whitelist = ler_whitelist_colar_calendario(self._db_path)
        usar_whitelist = bool(whitelist)
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
            if usar_whitelist:
                item.setCheckState(Qt.Checked if ativo in whitelist else Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)
            item.setForeground(QColor(Palette.TEXT_PRIMARY))
            self.lista_ativos.addItem(item)
        self.lista_ativos.blockSignals(False)
        self._aplicar_filtro_lista()
        self._on_search_ativos_debounced()

    def atualizar_resultados(self, resultados: list):
        self._dados_carregados = True
        self._resultados = resultados
        items = []
        for r in resultados:
            pnl_b3 = r.pnl_projetado - r.custo_b3
            pnl_liquido = pnl_b3 - r.custo_ir
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
                "custo_b3": r.custo_b3,
                "custo_ir": r.custo_ir,
                "pnl_b3": pnl_b3,
                "pnl_liquido": pnl_liquido,
                "capital_empregado": r.capital_empregado,
                "pct_retorno": r.pct_retorno,
                "pct_cdi": r.pct_cdi,
                "tipo_str": r.tipo.value,
                "viavel": r.viavel,
            })
        self.model.atualizar(items)

        ativos_atuais = set(
            self.lista_ativos.item(i).text()
            for i in range(1, self.lista_ativos.count())
        )
        novos_ativos = sorted(set(r.ativo for r in resultados if r.ativo not in ativos_atuais))
        if novos_ativos:
            whitelist = ler_whitelist_colar_calendario(self._db_path)
            usar_whitelist = bool(whitelist)
            self.lista_ativos.blockSignals(True)
            for ativo in novos_ativos:
                item = QListWidgetItem(ativo)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if usar_whitelist:
                    item.setCheckState(Qt.Checked if ativo in whitelist else Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked)
                item.setForeground(QColor(Palette.TEXT_PRIMARY))
                self.lista_ativos.addItem(item)
            self.lista_ativos.blockSignals(False)

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

        n_viaveis = sum(1 for r in resultados if r.viavel)
        if self._som_ativado and n_viaveis > 0:
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 150)

    def _abrir_regras(self):
        from src.ui.desktop.regras_dialog import RegrasDialog
        dlg = RegrasDialog("COLLAR_CALENDARIO", self._db_path, self)
        dlg.exec_()

    def _toggle_som(self, ativo: bool):
        self._som_ativado = ativo
        self.btn_bell.setToolTip("Som: ligado" if ativo else "Som: desligado")
