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

from src.domain.services.calendario_b3 import dc_to_du
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
    ("Calls", 55, "Quantidade de CALLs em ações (ratio × qtd_acao)"),
    ("Puts", 55, "Quantidade de PUTs em ações (ratio × qtd_acao)"),
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
    ("Detectado", 130, "Data/hora (Brasília) da detecção pelo monitor"),
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
            if col == 22:
                det = item.get("detectado_em")
                if det:
                    try:
                        from datetime import datetime
                        from zoneinfo import ZoneInfo
                        dt = datetime.fromisoformat(str(det))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                        local = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
                        return local.strftime("%d/%m/%Y %H:%M:%S")
                    except Exception:
                        return str(det)[:19] if det else "-"
                return "-"
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
            return Qt.AlignCenter if col < 3 or col == 6 or col == 22 else Qt.AlignRight if col >= 3 else Qt.AlignLeft
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
        self.btn_explicar = QPushButton("\U0001f4d6 Explicar")
        self.btn_explicar.setToolTip("An\u00e1lise detalhada da estrat\u00e9gia, MOD, BWB e breakevens")
        self.btn_explicar.clicked.connect(self._explicar_selecionado)
        btn_layout.addWidget(self.btn_explicar)
        self.btn_comparar = QPushButton("\u2696  Comparar Otimiza\u00e7\u00f5es")
        self.btn_comparar.setToolTip("Compara todos os est\u00e1gios do mesmo chassi lado a lado")
        self.btn_comparar.clicked.connect(self._comparar_estagios_chassi)
        btn_layout.addWidget(self.btn_comparar)
        self.btn_recarregar = QPushButton("\U0001f504 Recarregar")
        self.btn_recarregar.clicked.connect(self._carregar)
        btn_layout.addWidget(self.btn_recarregar)
        self.btn_limpar = QPushButton("\U0001f5d1  Limpar Estudos")
        self.btn_limpar.setStyleSheet(
            "QPushButton { color: #e74c3c; border-color: rgba(231,76,60,0.5); }"
            "QPushButton:hover { background-color: #3d1515; border-color: #e74c3c; }"
        )
        self.btn_limpar.clicked.connect(self._limpar_estudos)
        btn_layout.addWidget(self.btn_limpar)
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

    def _explicar_selecionado(self):
        index = self.table_view.currentIndex()
        if not index.isValid():
            QMessageBox.information(self, "Explicar", "Selecione uma linha na tabela primeiro.")
            return
        item = self.model._items[index.row()]
        try:
            from src.domain.services.calculadora_colar_calendario import (
                CalculadoraColarCalendario, ResultadoColarCalendario, TipoColarCalendario,
            )
            from datetime import date
            r = ResultadoColarCalendario(
                ativo=item.get("ativo", ""),
                vencimento_call=date.today(),
                vencimento_put=date.today(),
                dte_call=item.get("dte_original", 0),
                dte_put=item.get("dte_put", 0) or item.get("dte_original", 0),
                dte_extra=item.get("dte_extra", 0) or 0,
                strike_call=item.get("strike_call", 0),
                strike_put=item.get("strike_put", 0),
                cod_call=item.get("cod_call", ""),
                cod_put=item.get("cod_put", ""),
                preco_ativo=item.get("preco_ativo", 0),
                premio_call=item.get("premio_call", 0),
                premio_put=item.get("premio_put", 0),
                net_credito=item.get("net_credito", 0) or 0,
                iv_call=item.get("iv_call", 0),
                iv_put=item.get("iv_put", 0) or item.get("iv_call", 0),
                valor_put_venc_call=item.get("valor_put_venc_call", 0) or 0,
                pnl_stock=0.0,
                pnl_projetado=item.get("pnl_projetado", 0) or 0,
                capital_empregado=item.get("capital_empregado", 0) or 0,
                pct_retorno=item.get("pct_retorno", 0) or 0,
                pct_cdi=item.get("pct_cdi", 0),
                delta_total=item.get("delta_total", 0) or 0,
                theta_call=item.get("theta_call", 0) or 0,
                theta_put=item.get("theta_put", 0) or 0,
                theta_liquido=item.get("theta_liquido", 0) or 0,
                viavel=bool(item.get("viavel", 1)),
                tipo=TipoColarCalendario.NEUTRO,
                r=0.1425,
                custo_b3=item.get("custo_b3", 0) or 0,
                custo_ir=item.get("custo_ir", 0) or 0,
                pct_cdi_liquido=item.get("pct_cdi_liquido", 0) or 0,
                score=item.get("score", 0) or 0,
                risco_max=item.get("risco_max", 0) or 0,
                iv_rank=item.get("iv_rank", 0) or 0,
                iv_rank_call=item.get("iv_rank_call", 0) or 0,
                iv_rank_put=item.get("iv_rank_put", 0) or 0,
                vega_call=item.get("vega_call", 0) or 0,
                vega_put=item.get("vega_put", 0) or 0,
                vega_liquido=item.get("vega_liquido", 0) or 0,
                gamma_call=item.get("gamma_call", 0) or 0,
                gamma_put=item.get("gamma_put", 0) or 0,
                score_iv=item.get("score_iv", 0) or 0,
                preco_compra=item.get("preco_compra", 0) or 0,
                be_baixa=item.get("be_esq"),
                be_alta=item.get("be_dir"),
                be_baixa_intrinseco=None,
                be_alta_intrinseco=None,
                ratio_call=item.get("ratio_call", 1.0),
                ratio_put=item.get("ratio_put", 1.0),
                is_otimizado=True,
                estagio_otimizado=item.get("estagio", ""),
                qtd_acao=item.get("qtd_acao", 100),
                qtd_call=item.get("qtd_acao", 100),
                qtd_put=item.get("qtd_acao", 100),
                lado_protegido=item.get("lado_protegido"),
                custo_protecao_total=item.get("custo_protecao_total", 0) or 0,
                pnl_liquido_pos_protecao=item.get("pnl_liquido_pos_protecao", 0) or 0,
                strike_protecao_call=item.get("strike_protecao_call"),
                strike_protecao_put=item.get("strike_protecao_put"),
                qtd_protecao_call=item.get("qtd_protecao_call", 0) or 0,
                qtd_protecao_put=item.get("qtd_protecao_put", 0) or 0,
                custo_protecao_call=item.get("custo_protecao_call", 0) or 0,
                custo_protecao_put=item.get("custo_protecao_put", 0) or 0,
                viavel_protecao=bool(item.get("viavel", 0)),
            )
            html = CalculadoraColarCalendario.gerar_explicacao(r)
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Explicação — {r.ativo} | {r.estagio_otimizado}")
            dialog.setMinimumSize(700, 500)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(16, 16, 16, 16)
            texto = QTextEdit()
            texto.setReadOnly(True)
            texto.setHtml(html)
            texto.setStyleSheet("background-color: #15152a; color: #e0e0e0; border: 1px solid #333; border-radius: 4px; font-size: 10pt; padding: 12px;")
            layout.addWidget(texto, stretch=1)
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            btn_close = QPushButton("Fechar")
            btn_close.clicked.connect(dialog.close)
            btn_row.addWidget(btn_close)
            layout.addLayout(btn_row)
            dialog.exec_()
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Erro", f"Falha ao gerar explicação:\n{e}\n\n{traceback.format_exc()}")

    def _comparar_estagios_chassi(self):
        index = self.table_view.currentIndex()
        if not index.isValid():
            QMessageBox.information(self, "Comparar", "Selecione uma linha na tabela primeiro.")
            return
        item = self.model._items[index.row()]
        id_chassi = item.get("id_chassi", "")
        ativo = item.get("ativo", "")

        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM historico_simulacoes WHERE id_chassi = ? ORDER BY estagio",
            (id_chassi,)
        ).fetchall()
        conn.close()

        if not rows:
            QMessageBox.information(self, "Comparar", "Nenhum registro encontrado para este chassi.")
            return

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QDialog, QVBoxLayout, QLabel
        from src.ui.desktop.theme import Palette

        estagios_order = ["Base", "Platô", "Proteção", "Rendimento"]
        records = {r["estagio"]: dict(r) for r in rows}
        base = records.get("Base", {})

        METRICS = [
            ("Ratio Call", "ratio_call", ".2f", False),
            ("Ratio Put", "ratio_put", ".2f", False),
            ("PnL (R$)", "pnl_projetado", ".2f", True),
            ("% CDI", "pct_cdi", ".2f", True),
            ("BE Esq", "be_esq", ".2f", False),
            ("BE Dir", "be_dir", ".2f", False),
            ("PnL −3σ", "pnl_cauda_esq", ".2f", True),
            ("PnL +3σ", "pnl_cauda_dir", ".2f", True),
            ("σ Esq", "sigma_esq_str", "s", False),
            ("σ Dir", "sigma_dir_str", "s", False),
            ("BWB", "lado_protegido", "s", False),
            ("K BWB C", "strike_protecao_call", ".2f", False),
            ("K BWB P", "strike_protecao_put", ".2f", False),
            ("Qtd BWB C", "qtd_protecao_call", ".0f", False),
            ("Qtd BWB P", "qtd_protecao_put", ".0f", False),
            ("Custo BWB", "custo_protecao_total", ".2f", False),
            ("PnL Pós-BWB", "pnl_liquido_pos_protecao", ".2f", True),
        ]

        table = QTableWidget(len(METRICS), len(estagios_order) + 1)
        table.setHorizontalHeaderLabels(["Métrica"] + estagios_order)
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)

        for row_idx, (metric_name, key, fmt, higher_is_better) in enumerate(METRICS):
            table.setItem(row_idx, 0, QTableWidgetItem(metric_name))

            values = []
            for e_idx, estagio in enumerate(estagios_order):
                rec = records.get(estagio, {})
                nonlocal_key = "pnl_liquido_pos_protecao" if key == "pnl_liquido_pos_protecao" else key

                if key in ("sigma_esq_str", "sigma_dir_str"):
                    be_key = "be_esq" if key == "sigma_esq_str" else "be_dir"
                    be_val = rec.get(be_key)
                    preco = rec.get("preco_ativo", 0) or 0
                    iv = rec.get("iv_call", 0) or 0
                    dte = rec.get("dte_original", 0) or 0
                    if be_val is not None and preco > 0 and iv > 0 and dte > 0:
                        iv_dec = iv / 100.0
                        one_sigma = preco * iv_dec * sqrt(dte / 365.0)
                        if one_sigma > 0:
                            val = f"{(be_val - preco) / one_sigma:+.2f}"
                        else:
                            val = "-"
                    else:
                        val = "-"
                elif fmt == "s":
                    val = rec.get(key, "-") or "-"
                else:
                    val = rec.get(key)
                    if val is None:
                        display = "-"
                    else:
                        try:
                            display = f"{float(val):{fmt}}"
                        except (ValueError, TypeError):
                            display = str(val)
                    values.append(float(val) if val is not None else None)
                    val = display

                item_w = QTableWidgetItem(str(val))
                item_w.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, e_idx + 1, item_w)

            numeric_vals = [(i, v) for i, v in enumerate(values) if v is not None]
            if len(numeric_vals) >= 2:
                if higher_is_better:
                    best_idx = max(numeric_vals, key=lambda x: x[1])[0]
                    worst_idx = min(numeric_vals, key=lambda x: x[1])[0]
                else:
                    best_idx = min(numeric_vals, key=lambda x: x[1])[0]
                    worst_idx = max(numeric_vals, key=lambda x: x[1])[0]
                for col in range(1, len(estagios_order) + 1):
                    if col - 1 == best_idx:
                        table.item(row_idx, col).setBackground(QColor(C_GREEN))
                        table.item(row_idx, col).setForeground(QColor("#ffffff"))
                    elif col - 1 == worst_idx:
                        table.item(row_idx, col).setBackground(QColor(C_RED))
                        table.item(row_idx, col).setForeground(QColor("#ffffff"))

        delta_row = len(METRICS)
        table.setRowCount(delta_row + 1)
        table.setItem(delta_row, 0, QTableWidgetItem("Δ PnL vs Base"))
        base_pnl = base.get("pnl_projetado", 0) or 0
        for e_idx, estagio in enumerate(estagios_order):
            rec = records.get(estagio, {})
            pnl = rec.get("pnl_projetado", 0) or 0
            delta = pnl - base_pnl if estagio != "Base" and pnl else 0
            color = C_GREEN if delta > 0 else C_RED if delta < 0 else C_TEXT
            item_d = QTableWidgetItem(f"{delta:+.2f}" if estagio != "Base" else "—")
            item_d.setTextAlignment(Qt.AlignCenter)
            if estagio != "Base":
                item_d.setBackground(QColor(color))
                item_d.setForeground(QColor("#ffffff"))
            table.setItem(delta_row, e_idx + 1, item_d)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setMinimumWidth(800)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Comparação de Estágios — {ativo} | {id_chassi}")
        dlg.setMinimumSize(900, 500)
        dlg.setStyleSheet(f"background-color: {C_BG}; color: {C_TEXT};")
        layout = QVBoxLayout(dlg)

        header = QLabel(f"<b>Chassi:</b> {id_chassi} &nbsp;|&nbsp; "
                        f"<b>Ativo:</b> {ativo} &nbsp;|&nbsp; "
                        f"<b>Spot:</b> R$ {base.get('preco_ativo', 0):.2f} &nbsp;|&nbsp; "
                        f"<b>Kc:</b> {base.get('strike_call', 0):.2f} &nbsp;|&nbsp; "
                        f"<b>Kp:</b> {base.get('strike_put', 0):.2f}")
        header.setStyleSheet("font-size: 10pt; padding: 4px;")
        layout.addWidget(header)
        layout.addWidget(table)

        from src.ui.desktop.copy_utils import copiar_figura_clipboard
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        dlg.exec_()

    def _plot_payoff(self, r):
        from PySide6.QtWidgets import QMessageBox
        import traceback
        try:
            import numpy as np
            from scipy.stats import norm
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            from src.infrastructure.persistence.repositories.repositories import ParametroRepository
            from src.infrastructure.persistence.database import get_db_path

            db_path = get_db_path()
            S0 = r.get("preco_ativo", 0)
            Kc = r.get("strike_call", 0)
            Kp = r.get("strike_put", 0)
            Pc = r.get("premio_call", 0)
            Pp = r.get("premio_put", 0)
            iv_c = r.get("iv_call", 0) / 100.0
            iv_p_raw = r.get("iv_put", 0) or 0
            iv_p = (iv_p_raw / 100.0) if iv_p_raw > 0 else iv_c
            dte_call = r.get("dte_original", 0)
            dte_extra = r.get("dte_extra", 0) or 0
            T_call = dc_to_du(None, None, dte_call) / 252.0
            T_rem = dc_to_du(None, None, dte_extra) / 252.0 if dte_extra > 0 else 0
            n = max(r.get("ratio_call", 1), 1)
            m = max(r.get("ratio_put", 1), 0.01)
            S_custo = r.get("preco_compra", 0) or S0
            qtd_a = r.get("qtd_acao", 100) or 100

            repo = ParametroRepository(db_path)
            param = repo.get_by_chave("taxa_cdi")
            rf = param.valor if param else 0.1450

            if S0 <= 0 or Kc <= 0 or Kp <= 0:
                QMessageBox.warning(self, "Grafico", "Dados insuficientes para gerar payoff.")
                return

            sigma_spot = S0 * iv_c * np.sqrt(T_call) if iv_c > 0 and T_call > 0 else S0 * 0.02
            s3_l = S0 - 3 * sigma_spot
            s3_r = S0 + 3 * sigma_spot
            x_min = min(Kp, S0, s3_l) * (0.92 if n > 1 else 0.95)
            x_max = max(Kc, S0, s3_r) * (1.08 if n > 1 else 1.05)
            x = np.linspace(x_min, x_max, 500)

            stock_pnl = np.minimum(x, Kc) - S_custo
            call_pnl = Pc * n
            naked_pnl = -(n - 1) * np.maximum(0, x - Kc)

            if T_rem > 0:
                dp1 = (np.log(x / Kp) + (rf + 0.5 * iv_p ** 2) * T_rem) / (iv_p * np.sqrt(T_rem))
                dp2 = dp1 - iv_p * np.sqrt(T_rem)
                put_val = Kp * np.exp(-rf * T_rem) * norm.cdf(-dp2) - x * norm.cdf(-dp1)
            else:
                put_val = np.maximum(Kp - x, 0)
            put_pnl = m * put_val - m * Pp

            pnl = (stock_pnl + call_pnl + naked_pnl + put_pnl) * qtd_a

            # ── BWB historico ──
            strikes_call_str = r.get("strikes_bwb_call")
            strikes_put_str = r.get("strikes_bwb_put")
            lotes_b_call = r.get("lotes_bwb_call", 0) or 0
            lotes_b_put = r.get("lotes_bwb_put", 0) or 0
            custo_b_call = r.get("custo_borboleta_call", 0.0) or 0.0
            custo_b_put = r.get("custo_borboleta_put", 0.0) or 0.0
            bwb_call_pnl = np.zeros_like(x)
            bwb_put_pnl = np.zeros_like(x)
            if strikes_call_str and lotes_b_call > 0:
                try:
                    w1c, k_body_c, w2c = map(float, strikes_call_str.split(","))
                    bwb_call_pnl = (
                        +1 * np.maximum(0, x - w1c) * 100
                        - 2 * np.maximum(0, x - k_body_c) * 100
                        + 1 * np.maximum(0, x - w2c) * 100
                    ) * lotes_b_call - custo_b_call
                except Exception:
                    pass
            if strikes_put_str and lotes_b_put > 0:
                try:
                    w1p, k_body_p, w2p = map(float, strikes_put_str.split(","))
                    bwb_put_pnl = (
                        +1 * np.maximum(0, w1p - x) * 100
                        - 2 * np.maximum(0, k_body_p - x) * 100
                        + 1 * np.maximum(0, w2p - x) * 100
                    ) * lotes_b_put - custo_b_put
                except Exception:
                    pass
            pnl = pnl + bwb_call_pnl + bwb_put_pnl

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

            ax.axvline(S0, color=SPOT_CLR, linewidth=1.2, linestyle='--', alpha=0.6)
            ax.text(S0, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.02,
                    f'Spot={S0:.2f}', color=SPOT_CLR, fontsize=7, ha='center', alpha=0.7)

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

            for strike, nome, cor_s in [(Kp, 'Kp', RED), (Kc, 'Kc', GREEN)]:
                ax.axvline(strike, color=cor_s, linewidth=0.6, linestyle='--', alpha=0.3)
                ax.text(strike, ax.get_ylim()[0], f'{nome}={strike:.2f}',
                        color=cor_s, fontsize=6, ha='center', alpha=0.5)

            BWB_CLR = '#e67e22'
            if strikes_call_str and lotes_b_call > 0:
                try:
                    w1c, k_body_c, w2c = map(float, strikes_call_str.split(","))
                    for ks in [w1c, k_body_c, w2c]:
                        ax.axvline(ks, color=BWB_CLR, linewidth=0.5, linestyle='-.', alpha=0.5)
                except Exception:
                    pass
            if strikes_put_str and lotes_b_put > 0:
                try:
                    w1p, k_body_p, w2p = map(float, strikes_put_str.split(","))
                    for ks in [w1p, k_body_p, w2p]:
                        ax.axvline(ks, color=BWB_CLR, linewidth=0.5, linestyle='-.', alpha=0.5)
                except Exception:
                    pass

            ax.set_xlabel('Preço do Ativo (R$)', color=TEXT_C, fontsize=8)
            ax.set_ylabel('PnL (R$)', color=TEXT_C, fontsize=8)
            ax.tick_params(colors=TEXT_C, labelsize=7)
            for spine in ax.spines.values():
                spine.set_color('#2d2d44')

            titulo = f'{r.get("ativo","")} | {r.get("estagio","")} | rC={n:.2f} rP={m:.2f}'
            lado_bwb = r.get("lado_protegido")
            if lado_bwb and lado_bwb not in ("nenhum", None):
                titulo += " + BWB"
            ax.set_title(titulo, color=ACCENT, fontsize=9, fontweight='bold')

            fig.tight_layout()

            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
            from src.ui.desktop.theme import Palette

            dlg = QDialog(self)
            dlg.setWindowTitle(f"Payoff - {r.get('id_chassi','')} / {r.get('estagio','')}")
            dlg.setMinimumSize(920, 600)
            dlg.setStyleSheet("background-color: #0d0d0d;")
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(8, 8, 8, 8)
            canvas = FigureCanvas(fig)
            layout.addWidget(canvas, stretch=1)

            cod_c = r.get("cod_call", "")
            cod_p = r.get("cod_put", "")
            cap_txt = f"Capital: R$ {r.get('capital_empregado', 0):.2f}" if r.get("capital_empregado") else ""
            pnl_proj = r.get("pnl_projetado", 0)
            pct_ret = r.get("pct_retorno", 0)
            pct_cdi_v = r.get("pct_cdi", 0)
            be_parts = []
            if be_esq is not None:
                be_parts.append(f"BE Esq: R$ {be_esq:.2f}")
            if be_dir is not None:
                be_parts.append(f"BE Dir: R$ {be_dir:.2f}")
            be_str = " | ".join(be_parts)

            bwb_txt = ""
            if strikes_call_str and lotes_b_call > 0:
                bwb_txt += f"<br><b>BWB Call:</b> {strikes_call_str} x{lotes_b_call} lotes — R$ {custo_b_call:.2f}"
            if strikes_put_str and lotes_b_put > 0:
                bwb_txt += f"<br><b>BWB Put:</b> {strikes_put_str} x{lotes_b_put} lotes — R$ {custo_b_put:.2f}"

            footer = QLabel(
                f"<b>Comprar Ativo:</b> R$ {S_custo:.2f} × {qtd_a} un = R$ {S_custo * qtd_a:.2f}<br>"
                f"<b>Vender Call:</b> {cod_c} K={Kc:.2f} — +R$ {Pc:.2f} × {int(n * qtd_a)} ações = R$ {Pc * n * qtd_a:.2f}<br>"
                f"<b>Comprar Put:</b> {cod_p} K={Kp:.2f} — −R$ {Pp:.2f} × {int(m * qtd_a)} ações = R$ {Pp * m * qtd_a:.2f}"
                + bwb_txt
                + f"<br><b>{cap_txt}</b>  |  "
                f"<b>PnL Proj:</b> R$ {pnl_proj:.2f} ({pct_ret:.2f}% / {pct_cdi_v:.2f}x CDI)"
                f"{'  |  ' + be_str if be_str else ''}"
            )
            footer.setStyleSheet(f"""
                QLabel {{ color: {Palette.TEXT_SECONDARY}; font-size: 8pt; font-family: Consolas; padding: 4px 0; }}
            """)
            footer.setTextFormat(Qt.RichText)
            layout.addWidget(footer)

            from src.ui.desktop.copy_utils import salvar_figura_arquivo
            btn_row = QHBoxLayout()
            btn_salvar = QPushButton("💾 Salvar PNG")
            btn_salvar.setAutoDefault(False)
            btn_salvar.clicked.connect(lambda: salvar_figura_arquivo(fig, self))
            btn_row.addWidget(btn_salvar)
            btn_row.addStretch()
            btn_fechar = QPushButton("Fechar")
            btn_fechar.setAutoDefault(False)
            btn_fechar.clicked.connect(dlg.close)
            btn_row.addWidget(btn_fechar)
            layout.addLayout(btn_row)
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
                ORDER BY detectado_em DESC, estagio
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
                d["qtd_calls"] = max(100, int(r["ratio_call"] * qtd_acao + 0.5))
                d["qtd_puts"] = max(0, int(r["ratio_put"] * qtd_acao + 0.5))

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
                du_orig = dc_to_du(None, None, r["dte_original"])
                s2_l = r["preco_ativo"] * (1 - 2 * iv_dec * sqrt(du_orig / 252.0))
                s2_r = r["preco_ativo"] * (1 + 2 * iv_dec * sqrt(du_orig / 252.0))
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

    def _limpar_estudos(self):
        reply = QMessageBox.question(
            self, "Confirmar",
            "Tem certeza que deseja apagar TODOS os estudos?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            db_path = get_db_path()
            conn = sqlite3.connect(str(db_path))
            conn.execute("DELETE FROM historico_simulacoes")
            conn.commit()
            conn.close()
            self._carregar()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao limpar estudos:\n{e}")
