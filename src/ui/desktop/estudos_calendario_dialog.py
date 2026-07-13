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
    ("Chassi", 70, "ID único do grupo de otimização"),
    ("Ativo", 60, "Código do ativo B3"),
    ("Est\u00e1gio", 90, "Base=original, Platô=simetria, Proteção=sem BE esq, Rendimento=maior range"),
    ("Pre\u00e7o", 60, "Preço atual do ativo (R$)"),
    ("Kc", 60, "Strike da CALL vendida"),
    ("Kp", 60, "Strike da PUT comprada"),
    ("DTE", 36, "Dias até o vencimento (Days To Expiry)"),
    ("rC", 36, "Ratio CALL: qtd calls vendidas por ação"),
    ("rP", 36, "Ratio PUT: qtd puts compradas por ação"),
    ("Lotes C", 55, "Contratos de CALL (arredondado p/ lote B3)"),
    ("Lotes P", 55, "Contratos de PUT (arredondado p/ lote B3)"),
    ("BE esq", 65, "Breakeven esquerdo: preço onde PnL=0 no lado inferior"),
    ("BE dir", 65, "Breakeven direito: preço onde PnL=0 no lado superior"),
    ("%CDI", 55, "Retorno percentual do CDI no período"),
    ("PnL -3\u03c3", 70, "PnL na cauda esquerda em -3σ (R$)"),
    ("PnL +3\u03c3", 70, "PnL na cauda direita em +3σ (R$)"),
    ("\u03c3 esq", 55, "Desvios-padrão do spot até o BE esquerdo"),
    ("\u03c3 dir", 55, "Desvios-padrão do spot até o BE direito"),
    ("\u03c3$ esq", 65, "Distância em R$ do spot até o BE esquerdo"),
    ("\u03c3$ dir", 65, "Distância em R$ do spot até o BE direito"),
    ("Piso 2\u03c3", 65, "Menor PnL dentro de ±2σ (R$); negativo=risco)"),
    ("# ciclos", 55, "Quantas vezes este chassi foi registrado"),
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
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return COLUMNS[section][0]
            if role == Qt.ToolTipRole:
                return COLUMNS[section][2]
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
        for i, (_, w, _) in enumerate(COLUMNS):
            header.resizeSection(i, w)
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.verticalHeader().hide()
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
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

    def _on_row_double_clicked(self, index):
        if not index.isValid():
            return
        item = self.model._items[index.row()]
        self._plot_payoff(item)

    def _plot_payoff(self, r):
        from PySide6.QtWidgets import QMessageBox
        import traceback
        try:
            import numpy as np
            from scipy.stats import norm
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure

            # Extrair dados
            S0 = r.get("preco_ativo", 0)
            Kc = r.get("strike_call", 0)
            Kp = r.get("strike_put", 0)
            Pc = r.get("premio_call", 0)
            Pp = r.get("premio_put", 0)
            iv_c = r.get("iv_call", 0) / 100.0
            T_call = r.get("dte_original", 0) / 365.0
            T_rem = 0  # sem segunda perna no historico_simulacoes
            n = r.get("ratio_call", 1)
            m = r.get("ratio_put", 1)
            S_custo = r.get("preco_compra", 0) or S0

            if S0 <= 0 or Kc <= 0 or Kp <= 0:
                QMessageBox.warning(self, "Grafico", "Dados insuficientes para gerar payoff.")
                return

            # Range de precos
            sigma_spot = S0 * iv_c * np.sqrt(T_call) if iv_c > 0 and T_call > 0 else S0 * 0.02
            x_min = min(Kp, S0) * 0.92
            x_max = max(Kc, S0) * 1.08
            x = np.linspace(x_min, x_max, 500)

            # PnL: stock + calls + puts
            stock_pnl = np.minimum(x, Kc) - S_custo
            call_pnl = Pc * n
            naked_pnl = -(n - 1) * np.maximum(0, x - Kc)
            put_pnl = m * np.maximum(Kp - x, 0) - m * Pp
            pnl = stock_pnl + call_pnl + naked_pnl + put_pnl

            # Cores
            BG = '#0d0d0d'; TEXT_C = '#c0c0c0'; RED = '#ff3355'
            ACCENT = '#ffc107'; GREEN = '#4caf50'; SPOT_CLR = '#42a5f5'
            SIGMA_C = '#6c5ce7'

            fig = Figure(figsize=(9, 5), facecolor=BG)
            ax = fig.add_subplot(111, facecolor=BG)

            for i in range(len(x) - 1):
                mid = (pnl[i] + pnl[i + 1]) / 2
                cor = GREEN if mid >= 0 else RED
                ax.plot(x[i:i + 2], pnl[i:i + 2], color=cor, linewidth=2.5, solid_capstyle='round')

            ax.axhline(0, color=ACCENT, linewidth=0.8, linestyle=':', alpha=0.5)

            # Spot
            ax.axvline(S0, color=SPOT_CLR, linewidth=1.2, linestyle='--', alpha=0.6)
            ax.text(S0, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.02,
                    f'Spot={S0:.2f}', color=SPOT_CLR, fontsize=7, ha='center', alpha=0.7)

            # Breakevens
            be_esq = r.get("be_esq")
            be_dir = r.get("be_dir")
            if be_esq is not None:
                ax.axvline(be_esq, color=SIGMA_C, linewidth=1, linestyle=':', alpha=0.6)
                ax.text(be_esq, ax.get_ylim()[1] * 0.9, f'BEesq={be_esq:.2f}',
                        color=SIGMA_C, fontsize=6.5, ha='center', rotation=90, alpha=0.7)
            if be_dir is not None:
                ax.axvline(be_dir, color=SIGMA_C, linewidth=1, linestyle=':', alpha=0.6)
                ax.text(be_dir, ax.get_ylim()[1] * 0.9, f'BEdir={be_dir:.2f}',
                        color=SIGMA_C, fontsize=6.5, ha='center', rotation=90, alpha=0.7)

            # Strikes
            for strike, nome, cor_s in [(Kp, 'Kp', RED), (Kc, 'Kc', GREEN)]:
                ax.axvline(strike, color=cor_s, linewidth=0.6, linestyle='--', alpha=0.3)
                ax.text(strike, ax.get_ylim()[0], f'{nome}={strike:.2f}',
                        color=cor_s, fontsize=6, ha='center', alpha=0.5)

            ax.set_xlabel('Preço do Ativo (R$)', color=TEXT_C, fontsize=8)
            ax.set_ylabel('PnL (R$)', color=TEXT_C, fontsize=8)
            ax.tick_params(colors=TEXT_C, labelsize=7)
            for spine in ax.spines.values():
                spine.set_color('#2d2d44')

            titulo = f'{r.get("ativo","")} | {r.get("estagio","")} | rC={n:.2f} rP={m:.2f}'
            ax.set_title(titulo, color=ACCENT, fontsize=9, fontweight='bold')

            fig.tight_layout()

            from PySide6.QtWidgets import QDialog, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Payoff - {r.get('id_chassi','')} / {r.get('estagio','')}")
            dlg.resize(800, 500)
            dlg.setStyleSheet("background-color: #0d0d0d;")
            lay = QVBoxLayout(dlg)
            canvas = FigureCanvas(fig)
            lay.addWidget(canvas)
            dlg.exec_()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao gerar grafico:\n{e}\n{traceback.format_exc()}")

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

                # Quantities (lots) from actual qtd_acao
                qtd_acao = r["qtd_acao"] if r["qtd_acao"] else 100
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
