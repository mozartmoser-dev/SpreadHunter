from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QHeaderView, QAbstractItemView, QTextEdit, QSplitter,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.ui.desktop.mpp_table_model import MppTableModel
from src.ui.desktop.theme import Palette


class MppDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("MPP — Motor de Priorização de Pescaria")
        self.setMinimumSize(900, 500)
        self.resize(1000, 600)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Palette.BG_DARK};
            }}
            QLabel {{
                color: {Palette.TEXT_PRIMARY};
                font-size: 9pt;
            }}
            QTextEdit {{
                background-color: {Palette.BG_BASE};
                color: {Palette.TEXT_SECONDARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }}
        """)

        self._model = MppTableModel()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QLabel("Ranking de Pescaria — Boxes ordenados por Score Final")
        header.setStyleSheet(f"color: {Palette.CYAN}; font-size: 11pt; font-weight: bold;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Vertical)

        table_container = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setModel(self._model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSortingEnabled(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().hide()
        self.table_view.setShowGrid(True)
        font = QFont("Consolas", 9)
        self.table_view.setFont(font)
        self.table_view.setStyleSheet(f"""
            QTableView {{
                background-color: {Palette.BG_DARK};
                alternate-background-color: {Palette.BG_BASE};
                border: 1px solid {Palette.BORDER};
                gridline-color: {Palette.BORDER};
                selection-background-color: {Palette.BG_RAISED};
            }}
            QHeaderView::section {{
                background-color: {Palette.BG_BASE};
                color: {Palette.TEXT_MUTED};
                border: 1px solid {Palette.BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """)
        self.table_view.selectionModel().selectionChanged.connect(self._on_selecao)
        splitter.addWidget(self.table_view)

        details_container = QVBoxLayout()
        details_header = QLabel("Detalhes da Oportunidade")
        details_header.setStyleSheet(f"color: {Palette.CYAN}; font-size: 10pt; font-weight: bold;")
        details_container.addWidget(details_header)

        self._details_edit = QTextEdit()
        self._details_edit.setReadOnly(True)
        self._details_edit.setMinimumHeight(100)
        self._details_edit.setPlaceholderText("Selecione um box para ver detalhes...")
        details_container.addWidget(self._details_edit)

        details_widget = QLabel()
        details_widget.setLayout(details_container)
        splitter.addWidget(details_widget)

        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_forcar = QPushButton("Forçar Atualização")
        self.btn_forcar.setStyleSheet(f"""
            QPushButton {{
                background-color: {Palette.BG_RAISED};
                color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.ACCENT_BLUE}66;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Palette.BG_HOVER};
            }}
        """)
        self.btn_forcar.clicked.connect(self._forcar_atualizacao)
        btn_layout.addWidget(self.btn_forcar)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setStyleSheet(f"""
            QPushButton {{
                background-color: {Palette.BG_RAISED};
                color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Palette.BG_HOVER};
            }}
        """)
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def atualizar(self, boxes: list, mres: list):
        self._model.atualizar(boxes, mres)

    def _on_selecao(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            return
        row = indexes[0].row()
        box = self._model.get_box(row)
        mre = self._model.get_mre(row)
        self._exibir_detalhes(box, mre)

    def _exibir_detalhes(self, box, mre):
        if not box:
            self._details_edit.setText("Nenhum box selecionado.")
            return

        lines = []
        lines.append(f"Ativo: {box.ativo}")
        lines.append(f"Box: {box.strike1:.0f} x {box.strike2:.0f}")
        lines.append(f"Vencimento: {box.vencimento}")
        lines.append(f"Score Final: {box.score_final_pct:.0f}")
        lines.append(f"Score Estrutural: {box.score_estrutural_box:.4f}")
        lines.append(f"Score Instantâneo: {box.score_instantaneo_box:.4f}")
        lines.append(f"Nível de Risco: {box.nivel_risco}")
        lines.append(f"Erro de Paridade: {box.erro_paridade_box:.4f}")
        lines.append(f"Spread Médio: {box.spread_medio:.4f}")
        lines.append(f"Profundidade Mínima: {box.profundidade_min:.4f}")
        lines.append(f"Persistência: {box.persistencia_ciclos} ciclos")
        lines.append(f"Justificativa: {box.justificativa}")
        lines.append("")

        if mre:
            lines.append("--- RECOMENDAÇÃO MRE ---")
            lines.append(f"Isca Recomendada: {mre.isca_recomendada}")
            lines.append(f"IP da Isca: {mre.ip_isca:.2f}")
            lines.append(f"Lote Sugerido: {mre.lote_sugerido}")
            lines.append(f"Confiança de Completar: {mre.confianca_completar:.1%}")
            lines.append(f"Nível: {mre.nivel_recomendacao}")
            lines.append(f"Justificativa: {mre.justificativa}")

        self._details_edit.setText("\n".join(lines))

    def _forcar_atualizacao(self):
        if hasattr(self, 'parent') and self.parent():
            main = self.parent()
            if hasattr(main, '_worker') and hasattr(main._worker, '_processar_mpp'):
                main._worker._mpp_cycle = 0
                main._worker._processar_mpp(main._worker._rtd_main)
