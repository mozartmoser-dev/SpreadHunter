"""Estudos Calendário — comparação Base vs Platô vs Proteção vs Rendimento."""
import logging
import sqlite3
from math import sqrt
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QTimer
from PySide6.QtGui import QFont, QColor

from src.infrastructure.persistence.database import get_db_path
from src.ui.desktop.column_utils import salvar_ordem_colunas, limpar_e_restaurar_colunas

logger = logging.getLogger(__name__)

# Color constants (matching theme)
C_BG = "#1a1a2e"
C_TABLE = "#1a1a2e"
C_ALT = "#1e1e34"
C_TEXT = "#e0e0e0"
C_HDR = "#0f0f23"
C_ACCENT = "#00f2ff"
C_BORDER = "#2d2d44"
C_GREEN = "#2ecc71"
C_RED = "#e74c3c"
C_YELLOW = "#f1c40f"
C_ORANGE = "#f39c12"
C_BLUE = "#4a90d9"

COLUMNS = [
    ("Chassi", 70),
    ("Ativo", 60),
    ("Est\u00e1gio", 90),
    ("Pre\u00e7o", 60),
    ("Kc", 60),
    ("Kp", 60),
    ("DTE", 36),
    ("rC", 36),
    ("rP", 36),
    ("Qtd Calls", 60),
    ("Qtd Puts", 60),
    ("BE esq", 65),
    ("BE dir", 65),
    ("%CDI", 55),
    ("PnL -3\u03c3", 70),
    ("PnL +3\u03c3", 70),
    ("\u03c3 esq", 55),
    ("\u03c3 dir", 55),
    ("\u03c3$ esq", 65),
    ("\u03c3$ dir", 65),
    ("Piso 2\u03c3", 65),
    ("# ciclos", 55),
]


class EstudosCalendarioTableModel(QAbstractTableModel):
    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0: return str(item.get("id_chassi", ""))
            if col == 1: return str(item.get("ativo", ""))
            if col == 2: return str(item.get("estagio", ""))
            if col == 3: return f'{item.get("preco_ativo", 0):.2f}'
            if col == 4: return f'{item.get("strike_call", 0):.2f}'
            if col == 5: return f'{item.get("strike_put", 0):.2f}'
            if col == 6: return str(item.get("dte_original", ""))
            if col == 7: return f'{item.get("ratio_call", 0):.2f}'
            if col == 8: return f'{item.get("ratio_put", 0):.2f}'
            if col == 9: return str(item.get("qtd_calls", ""))
            if col == 10: return str(item.get("qtd_puts", ""))
            if col == 11: return item.get("be_esq_str", "-")
            if col == 12: return item.get("be_dir_str", "-")
            if col == 13: return f'{item.get("pct_cdi", 0):.2f}'
            if col == 14: return item.get("pnl_esq_str", "-")
            if col == 15: return item.get("pnl_dir_str", "-")
            if col == 16: return item.get("sigma_esq_str", "-")
            if col == 17: return item.get("sigma_dir_str", "-")
            if col == 18: return item.get("sigma_monet_esq_str", "-")
            if col == 19: return item.get("sigma_monet_dir_str", "-")
            if col == 20: return item.get("piso_2s_str", "-")
            if col == 21: return str(item.get("n_ciclos", ""))
        if role == Qt.BackgroundRole:
            estagio = item.get("estagio", "")
            if estagio == "Base":
                return QColor(55, 45, 20)      # amarelo escuro
            if estagio in ("Plat\u00f4", "Prote\u00e7\u00e3o", "Rendimento"):
                return QColor(35, 25, 50)      # roxo escuro
            return None
        if role == Qt.ForegroundRole:
            cdi = item.get("pct_cdi", 0)
            if col == 13 and isinstance(cdi, (int, float)):
                return QColor(C_GREEN) if cdi >= 2.0 else QColor(C_ORANGE) if cdi >= 1.0 else QColor(C_RED)
            estagio = item.get("estagio", "")
            if col == 2:
                pal = {"Base": C_YELLOW, "Rendimento": C_ORANGE, "Plat\u00f4": C_BLUE, "Prote\u00e7\u00e3o": C_GREEN}
                return QColor(pal.get(estagio, C_TEXT))
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter if col < 3 else Qt.AlignRight if col >= 3 else Qt.AlignLeft
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section][0]
        return None

    def atualizar(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class EstudosCalendarioDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Estudos Calendário — Comparação de Estágios")
        self.resize(1200, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self._setup_style()
        self._setup_ui()
        self._carregar()

    def _setup_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C_BG}; color: {C_TEXT}; }}
            QTableView {{
                background-color: {C_TABLE}; color: {C_TEXT};
                border: 1px solid {C_BORDER}; gridline-color: {C_BORDER};
                font-family: 'Consolas', 'Courier New', monospace; font-size: 9pt;
                alternate-background-color: {C_ALT};
            }}
            QHeaderView::section {{
                background-color: {C_HDR}; color: {C_ACCENT};
                font-weight: bold; padding: 4px 6px; border: 1px solid {C_BORDER};
            }}
            QPushButton {{
                background-color: #2d2d44; color: {C_TEXT};
                border: 1px solid {C_BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d5c; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.table_view = QTableView()
        self.model = EstudosCalendarioTableModel()
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.setFont(QFont("Consolas", 9))
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setDragEnabled(True)
        KEY = "estudos_calendario_order"
        header.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header, KEY)))
        limpar_e_restaurar_colunas(header, KEY, "estudos_calendario_width")
        header.setSectionResizeMode(QHeaderView.Interactive)
        for i, (_, w) in enumerate(COLUMNS):
            header.resizeSection(i, w)
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.verticalHeader().hide()
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        self.btn_recarregar = QPushButton("\U0001f504 Recarregar")
        self.btn_recarregar.clicked.connect(self._carregar)
        btn_layout.addWidget(self.btn_recarregar)
        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_fechar)
        layout.addLayout(btn_layout)

    def _carregar(self):
        try:
            db_path = get_db_path()
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT * FROM historico_simulacoes
                ORDER BY id_chassi, estagio
            """).fetchall()

            # For each chassi, compute derived fields per row
            items = []
            for r in rows:
                d = dict(r)

                # Breakeven display
                d["be_esq_str"] = f'{r["be_esq"]:.2f}' if r["be_esq"] is not None else "INF"
                d["be_dir_str"] = f'{r["be_dir"]:.2f}' if r["be_dir"] is not None else "INF"

                # PnL tails
                d["pnl_esq_str"] = f'{r["pnl_cauda_esq"]:.2f}' if r["pnl_cauda_esq"] is not None else "-"
                d["pnl_dir_str"] = f'{r["pnl_cauda_dir"]:.2f}' if r["pnl_cauda_dir"] is not None else "-"

                # Quantities (lots)
                qtd_acao = 100  # standard lot
                d["qtd_calls"] = max(1, int(r["ratio_call"] * qtd_acao / 100 + 0.5))
                d["qtd_puts"] = max(0, int(r["ratio_put"] * qtd_acao / 100 + 0.5))

                # Sigmas nominais
                iv_dec = r["iv_call"] / 100.0
                T = r["dte_original"] / 365.0
                one_sigma = r["preco_ativo"] * iv_dec * sqrt(T) if iv_dec > 0 and T > 0 else 1.0

                be_esq = r["be_esq"]
                be_dir = r["be_dir"]

                if be_esq is not None:
                    sig_e = (be_esq - r["preco_ativo"]) / one_sigma
                    d["sigma_esq_str"] = f"{sig_e:+.2f}"
                    # Monetary σ above CDI: how many R$ away from spot
                    d["sigma_monet_esq_str"] = f"{be_esq - r['preco_ativo']:+.2f}"
                else:
                    d["sigma_esq_str"] = "INF"
                    d["sigma_monet_esq_str"] = "INF"

                if be_dir is not None:
                    sig_d = (be_dir - r["preco_ativo"]) / one_sigma
                    d["sigma_dir_str"] = f"{sig_d:+.2f}"
                    d["sigma_monet_dir_str"] = f"{be_dir - r['preco_ativo']:+.2f}"
                else:
                    d["sigma_dir_str"] = "INF"
                    d["sigma_monet_dir_str"] = "INF"

                # Piso 2σ (minimum PnL at ±2σ)
                s2_l = r["preco_ativo"] * (1 - 2 * iv_dec * sqrt(T / 252 * 365))
                s2_r = r["preco_ativo"] * (1 + 2 * iv_dec * sqrt(T / 252 * 365))
                pnl_2l = r["pnl_cauda_esq"] if r["pnl_cauda_esq"] is not None else 0
                pnl_2r = r["pnl_cauda_dir"] if r["pnl_cauda_dir"] is not None else 0
                piso = min(pnl_2l, pnl_2r)
                d["piso_2s_str"] = f"{piso:.2f}"

                items.append(d)

            conn.close()
            self.model.atualizar(items)
            self.setWindowTitle(f"Estudos Calendário — {len(items)} registros ({len(set(i['id_chassi'] for i in items))} chassis)")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar dados:\n{e}")
